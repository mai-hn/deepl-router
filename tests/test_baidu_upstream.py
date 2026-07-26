import asyncio
import json

import httpx
import pytest

from deepl_router.upstreams import BaiduMTUpstream, UpstreamError

PROVIDER = {"id": 1, "name": "Baidu", "kind": "baidu", "endpoint": "https://aip.baidubce.com", "api_key": "client-id", "api_secret": "client-secret", "timeout_seconds": 20}


def run_with_transport(handler, coro_factory):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await coro_factory(client)

    return asyncio.run(run())


def make_handler(counters, token="token-1", translate_response=None, token_body=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if "/oauth/2.0/token" in str(request.url):
            counters["token"] = counters.get("token", 0) + 1
            return httpx.Response(200, json=token_body or {"access_token": token, "expires_in": 2592000})
        counters["translate"] = counters.get("translate", 0) + 1
        counters["last_url"] = str(request.url)
        counters["last_body"] = json.loads(request.content)
        return httpx.Response(200, json=translate_response or {"result": {"trans_result": [{"src": "hello", "dst": "你好"}], "from": "en", "to": "zh"}})

    return handler


def test_translate_fetches_token_then_translates():
    counters = {}
    upstream = BaiduMTUpstream()
    result = run_with_transport(make_handler(counters), lambda client: upstream.translate(client, PROVIDER, "hello", "ZH", "EN"))
    assert result.text == "你好"
    assert counters["token"] == 1
    assert counters["translate"] == 1
    assert "access_token=token-1" in counters["last_url"]
    assert counters["last_body"] == {"q": "hello", "from": "en", "to": "zh"}


def test_token_is_cached_between_calls():
    counters = {}
    upstream = BaiduMTUpstream()
    handler = make_handler(counters)

    async def run(client):
        await upstream.translate(client, PROVIDER, "hello", "ZH", "EN")
        return await upstream.translate(client, PROVIDER, "world", "JA", None)

    result = run_with_transport(handler, run)
    assert result.text == "你好"
    assert counters["token"] == 1
    assert counters["translate"] == 2
    assert counters["last_body"]["to"] == "jp"
    assert counters["last_body"]["from"] == "auto"


def test_token_error_body_raises():
    counters = {}
    upstream = BaiduMTUpstream()
    handler = make_handler(counters, token_body={"error": "invalid_client", "error_description": "unknown client id"})
    with pytest.raises(UpstreamError, match="invalid_client|unknown client id"):
        run_with_transport(handler, lambda client: upstream.translate(client, PROVIDER, "hello", "ZH", None))


def test_expired_token_triggers_refresh_and_retry():
    state = {"token_calls": 0, "translate_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/oauth/2.0/token" in str(request.url):
            state["token_calls"] += 1
            return httpx.Response(200, json={"access_token": f"token-{state['token_calls']}", "expires_in": 2592000})
        state["translate_calls"] += 1
        if state["translate_calls"] == 1:
            return httpx.Response(200, json={"error_code": 110, "error_msg": "Access token invalid"})
        return httpx.Response(200, json={"result": {"trans_result": [{"src": "hello", "dst": "你好"}]}})

    upstream = BaiduMTUpstream()
    result = run_with_transport(handler, lambda client: upstream.translate(client, PROVIDER, "hello", "ZH", None))
    assert result.text == "你好"
    assert state["token_calls"] == 2
    assert state["translate_calls"] == 2


def test_non_token_error_code_raises():
    counters = {}
    upstream = BaiduMTUpstream()
    handler = make_handler(counters, translate_response={"error_code": 17, "error_msg": "Open api daily request limit reached"})
    with pytest.raises(UpstreamError, match="17"):
        run_with_transport(handler, lambda client: upstream.translate(client, PROVIDER, "hello", "ZH", None))


def test_meta_registered():
    meta = BaiduMTUpstream.meta
    assert meta.kind == "baidu"
    assert meta.needs_secret is True
    assert meta.quota_type is None
