import asyncio
from pathlib import Path

import httpx

from deepl_router.router import ProviderRouter
from deepl_router.store import Store


def build_store(tmp_path: Path) -> Store:
    return Store(tmp_path / "router.db")


def test_store_masks_key(tmp_path):
    store = build_store(tmp_path)
    store.create_provider({"name": "Official", "kind": "deepl", "endpoint": "https://api.deepl.com", "api_key": "secret-1234", "priority": 1, "weight": 2, "enabled": True, "timeout_seconds": 20})
    item = store.providers()[0]
    assert item["key_hint"].endswith("1234")
    assert "api_key" not in item


def test_custom_provider_request_shape_and_fallback(tmp_path, monkeypatch):
    store = build_store(tmp_path)
    first = store.create_provider({"name": "Broken", "kind": "custom", "endpoint": "https://first.example", "api_key": "", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    second = store.create_provider({"name": "Works", "kind": "deeplx", "endpoint": "https://second.example", "api_key": "", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    calls = []

    async def fake_call(self, provider, text, target_lang, source_lang):
        calls.append(provider["id"])
        if provider["id"] == first["id"]:
            raise httpx.ConnectError("offline")
        from deepl_router.router import TranslationResult
        return TranslationResult("你好", "EN", provider["name"])

    monkeypatch.setattr(ProviderRouter, "_call_provider", fake_call)
    result = asyncio.run(ProviderRouter(store).translate("hello", "ZH", "EN"))
    assert result.text == "你好"
    assert result.provider == "Works"
    assert set(calls) == {first["id"], second["id"]}


def test_smooth_weighted_round_robin_prefers_higher_weight(tmp_path):
    store = build_store(tmp_path)
    store.create_provider({"name": "High", "kind": "custom", "endpoint": "https://high.example", "api_key": "", "priority": 1, "weight": 3, "enabled": True, "timeout_seconds": 20})
    store.create_provider({"name": "Low", "kind": "custom", "endpoint": "https://low.example", "api_key": "", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    router = ProviderRouter(store)
    picks = [router.order()[0]["name"] for _ in range(8)]
    assert picks.count("High") == 6
    assert picks.count("Low") == 2
