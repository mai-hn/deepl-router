from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .store import Store


class TranslationError(RuntimeError):
    pass


@dataclass
class TranslationResult:
    text: str
    detected_source_language: str | None
    provider: str


class ProviderRouter:
    def __init__(self, store: Store) -> None:
        self.store = store
        self._round_robin_weights: dict[tuple[int, tuple[tuple[int, int], ...]], dict[int, int]] = {}

    def candidates(self) -> list[dict[str, Any]]:
        return [p for p in self.store.providers(reveal_key=True) if p["enabled"]]

    def order(self) -> list[dict[str, Any]]:
        providers = self.candidates()
        if not providers:
            raise TranslationError("没有启用的上游通道")
        groups: dict[int, list[dict[str, Any]]] = {}
        for provider in providers:
            groups.setdefault(provider["priority"], []).append(provider)
        ordered: list[dict[str, Any]] = []
        for priority in sorted(groups):
            group = groups[priority]
            selected = self._next_weighted(group, priority)
            # The selected provider receives this request. The remaining providers are
            # deterministic fallbacks within the same priority group.
            ordered.append(selected)
            ordered.extend(provider for provider in group if provider["id"] != selected["id"])
        return ordered

    def _next_weighted(self, group: list[dict[str, Any]], priority: int) -> dict[str, Any]:
        """Pick the next channel using smooth weighted round-robin.

        For weights 5:1, the primary sequence is A, A, A, B, A, A ... rather
        than random sampling. The key includes the current group composition so
        editing a channel resets only that group's scheduler state.
        """
        signature = tuple(sorted((provider["id"], max(1, provider["weight"])) for provider in group))
        state_key = (priority, signature)
        current = self._round_robin_weights.setdefault(state_key, {provider_id: 0 for provider_id, _ in signature})
        total = sum(weight for _, weight in signature)
        by_id = {provider["id"]: provider for provider in group}
        selected_id: int | None = None
        selected_weight: int | None = None
        for provider_id, weight in signature:
            current[provider_id] = current.get(provider_id, 0) + weight
            if selected_weight is None or current[provider_id] > selected_weight:
                selected_id, selected_weight = provider_id, current[provider_id]
        assert selected_id is not None
        current[selected_id] -= total
        return by_id[selected_id]

    async def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> TranslationResult:
        settings = self.store.settings()
        errors: list[str] = []
        ordered = self.order()
        for index, provider in enumerate(ordered):
            started = time.perf_counter()
            try:
                result = await self._call_provider(provider, text, target_lang, source_lang)
                latency = round((time.perf_counter() - started) * 1000)
                self.store.set_health(provider["id"], "healthy", latency)
                return result
            except Exception as exc:  # noqa: BLE001 - failures must trigger fallback
                latency = round((time.perf_counter() - started) * 1000)
                message = str(exc)[:500]
                self.store.set_health(provider["id"], "unhealthy", latency, message)
                errors.append(f"{provider['name']}: {message}")
                if settings.get("fallback_enabled", "true") != "true" or index == len(ordered) - 1:
                    break
        raise TranslationError("所有通道请求失败：" + "；".join(errors))

    async def check(self, provider: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            await self._call_provider(provider, "health check", "ZH", "EN")
            latency = round((time.perf_counter() - started) * 1000)
            self.store.set_health(provider["id"], "healthy", latency)
            return {"ok": True, "latency_ms": latency}
        except Exception as exc:  # noqa: BLE001
            latency = round((time.perf_counter() - started) * 1000)
            self.store.set_health(provider["id"], "unhealthy", latency, str(exc)[:500])
            return {"ok": False, "latency_ms": latency, "error": str(exc)}

    async def _call_provider(self, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        timeout = httpx.Timeout(float(provider["timeout_seconds"]))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            if provider["kind"] == "deepl":
                return await self._deepl(client, provider, text, target_lang, source_lang)
            return await self._json_translate(client, provider, text, target_lang, source_lang)

    async def _deepl(self, client: httpx.AsyncClient, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        endpoint = provider["endpoint"].rstrip("/")
        if not endpoint.endswith("/v2/translate"):
            endpoint += "/v2/translate"
        data = {"text": [text], "target_lang": target_lang}
        if source_lang:
            data["source_lang"] = source_lang
        response = await client.post(
            endpoint,
            json=data,
            headers={"Authorization": f"DeepL-Auth-Key {provider['api_key']}", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        body = response.json()
        translations = body.get("translations") or []
        if not translations or not translations[0].get("text"):
            raise TranslationError("DeepL 响应缺少 translations[0].text")
        item = translations[0]
        return TranslationResult(item["text"], item.get("detected_source_language"), provider["name"])

    async def _json_translate(self, client: httpx.AsyncClient, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        endpoint = provider["endpoint"].rstrip("/")
        if not endpoint.endswith("/translate"):
            endpoint += "/translate"
        headers = {"Content-Type": "application/json"}
        if provider["api_key"]:
            headers["Authorization"] = f"Bearer {provider['api_key']}"
        payload = {"text": text, "target_lang": target_lang, "source_lang": source_lang or "auto"}
        response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
        # DLX deployments and common custom adapters expose one of these response shapes.
        translated = body.get("text") or body.get("data") or body.get("translation")
        if isinstance(translated, dict):
            translated = translated.get("text") or translated.get("translation")
        if not isinstance(translated, str) or not translated:
            raise TranslationError("上游响应缺少可识别的译文 text/data/translation 字段")
        return TranslationResult(translated, body.get("detected_source_language") or body.get("source_lang"), provider["name"])
