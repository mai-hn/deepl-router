from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from .store import Store


class TranslationError(RuntimeError):
    def __init__(self, message: str, attempts: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts or []


class UpstreamError(RuntimeError):
    def __init__(self, message: str, *, request: dict[str, Any], response: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.request = request
        self.response = response


@dataclass
class TranslationResult:
    text: str
    detected_source_language: str | None
    provider: str
    upstream_request: dict[str, Any] | None = None
    upstream_response: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] | None = None


class ProviderRouter:
    def __init__(self, store: Store) -> None:
        self.store = store
        self._round_robin_weights: dict[tuple[int, tuple[tuple[int, int], ...]], dict[int, int]] = {}

    def candidates(self) -> list[dict[str, Any]]:
        return [provider for provider in self.store.providers(reveal_key=True) if provider["enabled"]]

    def order(self) -> list[dict[str, Any]]:
        providers = self.candidates()
        if not providers:
            raise TranslationError("No enabled upstream route is available")
        groups: dict[int, list[dict[str, Any]]] = {}
        for provider in providers:
            groups.setdefault(provider["priority"], []).append(provider)
        ordered: list[dict[str, Any]] = []
        for priority in sorted(groups):
            group = groups[priority]
            selected = self._next_weighted(group, priority)
            ordered.append(selected)
            ordered.extend(provider for provider in group if provider["id"] != selected["id"])
        return ordered

    def _next_weighted(self, group: list[dict[str, Any]], priority: int) -> dict[str, Any]:
        signature = tuple(sorted((provider["id"], max(1, provider["weight"])) for provider in group))
        state_key = (priority, signature)
        current = self._round_robin_weights.setdefault(state_key, {provider_id: 0 for provider_id, _ in signature})
        total = sum(weight for _, weight in signature)
        selected_id: int | None = None
        selected_value: int | None = None
        for provider_id, weight in signature:
            current[provider_id] = current.get(provider_id, 0) + weight
            if selected_value is None or current[provider_id] > selected_value:
                selected_id, selected_value = provider_id, current[provider_id]
        assert selected_id is not None
        current[selected_id] -= total
        return next(provider for provider in group if provider["id"] == selected_id)

    async def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> TranslationResult:
        settings = self.store.settings()
        attempts: list[dict[str, Any]] = []
        errors: list[str] = []
        ordered = self.order()
        for index, provider in enumerate(ordered):
            started = time.perf_counter()
            try:
                result = await self._call_provider(provider, text, target_lang, source_lang)
                latency_ms = round((time.perf_counter() - started) * 1000)
                self.store.set_health(provider["id"], "healthy", latency_ms)
                attempts.append({
                    "provider": provider["name"], "kind": provider["kind"], "status": "success",
                    "latency_ms": latency_ms, "request": result.upstream_request or {},
                    "response": result.upstream_response or {},
                })
                result.attempts = attempts
                return result
            except Exception as exc:  # noqa: BLE001 - failures must trigger fallback
                latency_ms = round((time.perf_counter() - started) * 1000)
                message = str(exc)[:500]
                self.store.set_health(provider["id"], "unhealthy", latency_ms, message)
                upstream_request = exc.request if isinstance(exc, UpstreamError) else {"endpoint": provider["endpoint"]}
                upstream_response = exc.response if isinstance(exc, UpstreamError) else None
                attempts.append({
                    "provider": provider["name"], "kind": provider["kind"], "status": "failed",
                    "latency_ms": latency_ms, "request": upstream_request,
                    "response": upstream_response, "error": message,
                })
                errors.append(f"{provider['name']}: {message}")
                if settings.get("fallback_enabled", "true") != "true" or index == len(ordered) - 1:
                    break
        raise TranslationError("All upstream translation requests failed: " + "; ".join(errors), attempts)

    async def check(self, provider: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            await self._call_provider(provider, "health check", "ZH", "EN")
            latency_ms = round((time.perf_counter() - started) * 1000)
            self.store.set_health(provider["id"], "healthy", latency_ms)
            return {"ok": True, "latency_ms": latency_ms}
        except Exception as exc:  # noqa: BLE001
            latency_ms = round((time.perf_counter() - started) * 1000)
            self.store.set_health(provider["id"], "unhealthy", latency_ms, str(exc)[:500])
            return {"ok": False, "latency_ms": latency_ms, "error": str(exc)}

    async def _call_provider(self, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        timeout = httpx.Timeout(float(provider["timeout_seconds"]))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            if provider["kind"] == "deepl":
                return await self._deepl(client, provider, text, target_lang, source_lang)
            return await self._json_translate(client, provider, text, target_lang, source_lang)

    @staticmethod
    def _body(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:2000]

    async def _deepl(self, client: httpx.AsyncClient, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        endpoint = provider["endpoint"].rstrip("/")
        if not endpoint.endswith("/v2/translate"):
            endpoint += "/v2/translate"
        body = {"text": [text], "target_lang": target_lang}
        if source_lang:
            body["source_lang"] = source_lang
        request = {"method": "POST", "endpoint": endpoint, "body": body}
        try:
            response = await client.post(endpoint, json=body, headers={"Authorization": f"DeepL-Auth-Key {provider['api_key']}"})
            response_body = self._body(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), request=request, response={"status_code": exc.response.status_code, "body": self._body(exc.response)}) from exc
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(str(exc), request=request) from exc
        translations = response_body.get("translations") if isinstance(response_body, dict) else None
        if not translations or not translations[0].get("text"):
            raise UpstreamError("DeepL response is missing translations[0].text", request=request, response={"status_code": response.status_code, "body": response_body})
        item = translations[0]
        return TranslationResult(item["text"], item.get("detected_source_language"), provider["name"], request, {"status_code": response.status_code, "body": response_body})

    async def _json_translate(self, client: httpx.AsyncClient, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        endpoint = provider["endpoint"].rstrip("/")
        if not endpoint.endswith("/translate"):
            endpoint += "/translate"
        body = {"text": text, "target_lang": target_lang, "source_lang": source_lang or "auto"}
        headers = {"Content-Type": "application/json"}
        if provider["api_key"]:
            headers["Authorization"] = f"Bearer {provider['api_key']}"
        request = {"method": "POST", "endpoint": endpoint, "body": body}
        try:
            response = await client.post(endpoint, json=body, headers=headers)
            response_body = self._body(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), request=request, response={"status_code": exc.response.status_code, "body": self._body(exc.response)}) from exc
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(str(exc), request=request) from exc
        translated = response_body.get("text") or response_body.get("data") or response_body.get("translation") if isinstance(response_body, dict) else None
        if isinstance(translated, dict):
            translated = translated.get("text") or translated.get("translation")
        if not isinstance(translated, str) or not translated:
            raise UpstreamError("Upstream response has no text/data/translation field", request=request, response={"status_code": response.status_code, "body": response_body})
        return TranslationResult(translated, response_body.get("detected_source_language") or response_body.get("source_lang"), provider["name"], request, {"status_code": response.status_code, "body": response_body})
