import asyncio
import json

import httpx
import pytest

from deepl_router.upstreams import UPSTREAMS, AzureTranslatorUpstream, UpstreamError

PROVIDER = {"id": 1, "name": "Azure", "kind": "azure", "endpoint": "https://api.cognitive.microsofttranslator.com", "api_key": "azure-key", "api_secret": "", "region": "eastasia", "timeout_seconds": 20}


def run_with_transport(handler, coro_factory):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await coro_factory(client)

    return asyncio.run(run())


def test_translate_sends_key_region_and_parses_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[{"detectedLanguage": {"language": "en", "score": 1.0}, "translations": [{"text": "你好", "to": "zh-Hans"}]}])

    result = run_with_transport(handler, lambda client: UPSTREAMS["azure"].translate(client, PROVIDER, "hello", "ZH", None))
    assert result.text == "你好"
    assert result.detected_source_language == "en"
    assert "api-version=3.0" in captured["url"]
    assert "to=zh-Hans" in captured["url"]
    assert "from=" not in captured["url"]
    assert captured["headers"]["ocp-apim-subscription-key"] == "azure-key"
    assert captured["headers"]["ocp-apim-subscription-region"] == "eastasia"
    assert captured["body"] == [{"Text": "hello"}]


def test_translate_with_source_lang_and_global_region_omits_region_header():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        return httpx.Response(200, json=[{"translations": [{"text": "hi", "to": "en"}]}])

    provider = {**PROVIDER, "region": "global"}
    result = run_with_transport(handler, lambda client: UPSTREAMS["azure"].translate(client, provider, "你好", "EN", "ZH"))
    assert result.text == "hi"
    assert "from=zh-Hans" in captured["url"]
    assert "ocp-apim-subscription-region" not in captured["headers"]


def test_translate_raises_on_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": 401000, "message": "invalid key"}})

    with pytest.raises(UpstreamError):
        run_with_transport(handler, lambda client: UPSTREAMS["azure"].translate(client, PROVIDER, "hello", "ZH", None))


def test_meta_registered():
    meta = AzureTranslatorUpstream.meta
    assert meta.kind == "azure"
    assert meta.needs_region is True
    assert meta.quota_type is None
