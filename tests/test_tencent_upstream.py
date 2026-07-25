import asyncio
import sqlite3

import httpx

from deepl_router.store import Store
from deepl_router.upstreams import TencentCloudUpstream


def test_tencent_provider_masks_both_credentials(tmp_path):
    store = Store(tmp_path / "router.db")
    provider = store.create_provider({"name": "Tencent", "kind": "tencent", "endpoint": "https://tmt.tencentcloudapi.com", "api_key": "secret-id-1234", "api_secret": "secret-key", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    listed = store.providers()[0]
    assert provider["kind"] == "tencent"
    assert listed["key_hint"].endswith("1234")
    assert "api_key" not in listed
    assert "api_secret" not in listed


def test_existing_database_is_migrated_to_allow_tencent(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('deepl', 'deeplx', 'custom')),
            endpoint TEXT NOT NULL, api_key TEXT NOT NULL DEFAULT '', priority INTEGER NOT NULL DEFAULT 100,
            weight INTEGER NOT NULL DEFAULT 1, enabled INTEGER NOT NULL DEFAULT 1, timeout_seconds INTEGER NOT NULL DEFAULT 20,
            last_status TEXT NOT NULL DEFAULT 'unknown', last_latency_ms INTEGER, last_error TEXT,
            usage_character_count INTEGER, usage_character_limit INTEGER, usage_checked_at TEXT, usage_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
    store = Store(path)
    created = store.create_provider({"name": "Tencent", "kind": "tencent", "endpoint": "https://tmt.tencentcloudapi.com", "api_key": "id", "api_secret": "secret", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    assert created["kind"] == "tencent"


def test_tencent_text_translate_request_and_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"Response": {"TargetText": "你好", "RequestId": "request-id"}})

    provider = {"name": "Tencent", "endpoint": "https://tmt.tencentcloudapi.com", "api_key": "secret-id", "api_secret": "secret-key"}

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await TencentCloudUpstream().translate(client, provider, "hello", "ZH", "EN")

    result = asyncio.run(run())
    assert result.text == "你好"
    assert captured["headers"]["x-tc-action"] == "TextTranslate"
    assert captured["headers"]["authorization"].startswith("TC3-HMAC-SHA256 Credential=secret-id/")
    assert '"Source":"en"' in captured["body"]
    assert '"Target":"zh"' in captured["body"]
    assert "secret-key" not in str(result.upstream_request)
