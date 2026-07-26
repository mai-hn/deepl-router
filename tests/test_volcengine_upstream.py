import asyncio
import json

import httpx
import pytest

from deepl_router.upstreams import UPSTREAMS, UpstreamError, VolcengineUpstream, volc_sign_v4

PROVIDER = {"id": 1, "name": "Volc", "kind": "volcengine", "endpoint": "https://translate.volcengineapi.com", "api_key": "AKLTtest", "api_secret": "sk-secret", "timeout_seconds": 20}


def run_with_transport(handler, coro_factory):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await coro_factory(client)

    return asyncio.run(run())


def test_sign_v4_headers_and_scope():
    headers = volc_sign_v4("AK", "SK", service="translate", region="cn-north-1", host="translate.volcengineapi.com", path="/", method="POST", query={"Action": "TranslateText", "Version": "2020-06-01"}, payload=b"{}", timestamp=1700000000)
    assert headers["X-Date"] == "20231114T221320Z"
    assert headers["X-Content-Sha256"] == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    assert headers["Authorization"].startswith("HMAC-SHA256 Credential=AK/20231114/cn-north-1/translate/request,")
    assert "SignedHeaders=content-type;host;x-content-sha256;x-date" in headers["Authorization"]


def test_sign_v4_is_deterministic_and_key_sensitive():
    kwargs = dict(service="translate", region="cn-north-1", host="h", path="/", method="POST", query={"Action": "A", "Version": "1"}, payload=b"x", timestamp=1700000000)
    first = volc_sign_v4("AK", "SK", **kwargs)["Authorization"]
    second = volc_sign_v4("AK", "SK", **kwargs)["Authorization"]
    other = volc_sign_v4("AK", "SK2", **kwargs)["Authorization"]
    assert first == second
    assert first != other


def test_translate_parses_translation_list():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["headers"] = request.headers
        return httpx.Response(200, json={"TranslationList": [{"Translation": "你好", "DetectedSourceLanguage": "en"}]})

    result = run_with_transport(handler, lambda client: UPSTREAMS["volcengine"].translate(client, PROVIDER, "hello", "ZH", "EN"))
    assert result.text == "你好"
    assert "Action=TranslateText" in captured["url"]
    assert "Version=2020-06-01" in captured["url"]
    assert captured["body"] == {"TargetLanguage": "zh", "TextList": ["hello"], "SourceLanguage": "en"}
    assert captured["headers"]["x-date"].endswith("Z")
    assert "x-content-sha256" in captured["headers"]
    assert captured["headers"]["authorization"].startswith("HMAC-SHA256 Credential=AKLTtest/")
    assert "/cn-north-1/translate/request" in captured["headers"]["authorization"]
    assert "sk-secret" not in json.dumps(result.upstream_request)


def test_translate_raises_on_metadata_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ResponseMetadata": {"Error": {"Code": "AccessDenied", "Message": "nope"}}})

    with pytest.raises(UpstreamError, match="AccessDenied"):
        run_with_transport(handler, lambda client: UPSTREAMS["volcengine"].translate(client, PROVIDER, "hello", "ZH", None))


def test_query_quota_parses_available_balance():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["headers"] = request.headers
        return httpx.Response(200, json={"Result": {"AvailableBalance": "12.50", "CashBalance": "10.00"}})

    quota = run_with_transport(handler, lambda client: UPSTREAMS["volcengine"].query_quota(client, PROVIDER))
    assert quota.type == "balance"
    assert quota.amount == 12.5
    assert quota.currency == "CNY"
    assert captured["method"] == "GET"
    assert "open.volcengineapi.com" in captured["url"]
    assert "Action=QueryBalanceAcct" in captured["url"]
    assert "/cn-north-1/billing/request" in captured["headers"]["authorization"]


def test_meta_registered():
    meta = VolcengineUpstream.meta
    assert meta.kind == "volcengine"
    assert meta.needs_secret is True
    assert meta.quota_type == "balance"
