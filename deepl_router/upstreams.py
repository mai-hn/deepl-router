from __future__ import annotations

import hashlib
import hmac
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx


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


class Upstream(ABC):
    kind: str

    @abstractmethod
    async def translate(self, client: httpx.AsyncClient, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        raise NotImplementedError

    @staticmethod
    def response_body(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:2000]


class DeepLUpstream(Upstream):
    kind = "deepl"

    async def translate(self, client: httpx.AsyncClient, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        endpoint = provider["endpoint"].rstrip("/")
        if not endpoint.endswith("/v2/translate"):
            endpoint += "/v2/translate"
        body = {"text": [text], "target_lang": target_lang}
        if source_lang:
            body["source_lang"] = source_lang
        request = {"method": "POST", "endpoint": endpoint, "body": body}
        try:
            response = await client.post(endpoint, json=body, headers={"Authorization": f"DeepL-Auth-Key {provider['api_key']}"})
            response_body = self.response_body(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), request=request, response={"status_code": exc.response.status_code, "body": self.response_body(exc.response)}) from exc
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(str(exc), request=request) from exc
        translations = response_body.get("translations") if isinstance(response_body, dict) else None
        if not translations or not translations[0].get("text"):
            raise UpstreamError("DeepL response is missing translations[0].text", request=request, response={"status_code": response.status_code, "body": response_body})
        item = translations[0]
        return TranslationResult(item["text"], item.get("detected_source_language"), provider["name"], request, {"status_code": response.status_code, "body": response_body})


class JsonTranslateUpstream(Upstream):
    def __init__(self, kind: str) -> None:
        self.kind = kind

    async def translate(self, client: httpx.AsyncClient, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
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
            response_body = self.response_body(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), request=request, response={"status_code": exc.response.status_code, "body": self.response_body(exc.response)}) from exc
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(str(exc), request=request) from exc
        translated = (response_body.get("text") or response_body.get("data") or response_body.get("translation")) if isinstance(response_body, dict) else None
        if isinstance(translated, dict):
            translated = translated.get("text") or translated.get("translation")
        if not isinstance(translated, str) or not translated:
            raise UpstreamError("Upstream response has no text/data/translation field", request=request, response={"status_code": response.status_code, "body": response_body})
        return TranslationResult(translated, response_body.get("detected_source_language") or response_body.get("source_lang"), provider["name"], request, {"status_code": response.status_code, "body": response_body})


class TencentCloudUpstream(Upstream):
    kind = "tencent"
    service = "tmt"
    version = "2018-03-21"
    action = "TextTranslate"
    region = "ap-guangzhou"
    language_codes = {"ZH": "zh", "ZH-HANT": "zh-TW", "EN": "en", "JA": "ja", "KO": "ko", "DE": "de", "FR": "fr", "ES": "es", "RU": "ru", "IT": "it", "PT-BR": "pt", "PT-PT": "pt"}

    @staticmethod
    def _hmac(key: bytes, value: str) -> bytes:
        return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()

    def _language(self, value: str | None, default: str) -> str:
        return self.language_codes.get(value or "", default)

    async def translate(self, client: httpx.AsyncClient, provider: dict[str, Any], text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
        secret_id = provider.get("api_key", "")
        secret_key = provider.get("api_secret", "")
        if not secret_id or not secret_key:
            raise UpstreamError("Tencent Cloud requires SecretId and SecretKey", request={"method": "POST", "endpoint": provider["endpoint"]})

        endpoint = provider["endpoint"].rstrip("/") or "https://tmt.tencentcloudapi.com"
        parsed = urlparse(endpoint)
        host = parsed.netloc or "tmt.tencentcloudapi.com"
        path = parsed.path or "/"
        body = {"SourceText": text, "Source": self._language(source_lang, "auto"), "Target": self._language(target_lang, "zh"), "ProjectId": 0}
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = int(time.time())
        date = datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")
        canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{host}\n"
        signed_headers = "content-type;host"
        hashed_payload = hashlib.sha256(payload).hexdigest()
        canonical_request = f"POST\n{path}\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        credential_scope = f"{date}/{self.service}/tc3_request"
        string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        secret_date = self._hmac(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = self._hmac(secret_date, self.service)
        secret_signing = self._hmac(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        headers = {"Authorization": authorization, "Content-Type": "application/json; charset=utf-8", "Host": host, "X-TC-Action": self.action, "X-TC-Version": self.version, "X-TC-Timestamp": str(timestamp), "X-TC-Region": self.region}
        request = {"method": "POST", "endpoint": endpoint, "action": self.action, "body": body}
        try:
            response = await client.post(endpoint, content=payload, headers=headers)
            response_body = self.response_body(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), request=request, response={"status_code": exc.response.status_code, "body": self.response_body(exc.response)}) from exc
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(str(exc), request=request) from exc
        result = response_body.get("Response", {}) if isinstance(response_body, dict) else {}
        if result.get("Error"):
            error = result["Error"]
            raise UpstreamError(f"Tencent Cloud error: {error.get('Code', 'Unknown')} {error.get('Message', '')}", request=request, response={"status_code": response.status_code, "body": response_body})
        translated = result.get("TargetText")
        if not isinstance(translated, str) or not translated:
            raise UpstreamError("Tencent Cloud response is missing Response.TargetText", request=request, response={"status_code": response.status_code, "body": response_body})
        return TranslationResult(translated, source_lang, provider["name"], request, {"status_code": response.status_code, "body": response_body})


UPSTREAMS: dict[str, Upstream] = {
    "deepl": DeepLUpstream(),
    "deeplx": JsonTranslateUpstream("deeplx"),
    "tencent": TencentCloudUpstream(),
    "custom": JsonTranslateUpstream("custom"),
}
