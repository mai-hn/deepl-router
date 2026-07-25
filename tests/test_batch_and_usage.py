from fastapi.testclient import TestClient

import deepl_router.app as application
from deepl_router.store import Store


def test_batch_import_creates_deepl_and_dlx_routes(tmp_path, monkeypatch):
    temp_store = Store(tmp_path / "router.db")
    monkeypatch.setattr(application, "store", temp_store)
    client = TestClient(application.app)
    response = client.post("/api/providers/batch", json={
        "lines": "deepl | https://api-free.deepl.com | key-free:fx\ndlx | https://dlx.example.com |",
        "priority": 10,
    })
    assert response.status_code == 201
    providers = response.json()
    assert [provider["kind"] for provider in providers] == ["deepl", "deeplx"]
    assert providers[0]["priority"] == 10


def test_batch_import_rejects_invalid_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(application, "store", Store(tmp_path / "router.db"))
    response = TestClient(application.app).post("/api/providers/batch", json={"lines": "invalid | https://example.com | key"})
    assert response.status_code == 422
    assert "第 1 行类型" in response.json()["detail"]


def test_usage_endpoint_persists_usage(tmp_path, monkeypatch):
    temp_store = Store(tmp_path / "router.db")
    provider = temp_store.create_provider({"name": "Official", "kind": "deepl", "endpoint": "https://api.deepl.com", "api_key": "test", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    monkeypatch.setattr(application, "store", temp_store)

    async def fake_usage(item):
        temp_store.set_usage(item["id"], 120, 500000)
        return {"provider_id": item["id"], "character_count": 120, "character_limit": 500000}

    monkeypatch.setattr(application, "query_provider_usage", fake_usage)
    response = TestClient(application.app).post(f"/api/providers/{provider['id']}/usage")
    assert response.status_code == 200
    saved = temp_store.provider(provider["id"])
    assert saved["usage_character_count"] == 120
    assert saved["usage_character_limit"] == 500000


def test_batch_check_can_disable_and_delete_unhealthy_routes(tmp_path, monkeypatch):
    temp_store = Store(tmp_path / "router.db")
    healthy = temp_store.create_provider({"name": "Healthy", "kind": "deeplx", "endpoint": "https://healthy.example", "api_key": "", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    unhealthy = temp_store.create_provider({"name": "Unhealthy", "kind": "deeplx", "endpoint": "https://unhealthy.example", "api_key": "", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    monkeypatch.setattr(application, "store", temp_store)

    async def fake_check(provider):
        ok = provider["id"] == healthy["id"]
        temp_store.set_health(provider["id"], "healthy" if ok else "unhealthy", 12, None if ok else "offline")
        return {"ok": ok, "latency_ms": 12, **({} if ok else {"error": "offline"})}

    monkeypatch.setattr(application.router, "check", fake_check)
    client = TestClient(application.app)
    checked = client.post("/api/providers/check")
    assert checked.status_code == 200
    assert checked.json()["healthy"] == 1
    assert checked.json()["unhealthy"] == 1

    disabled = client.post("/api/providers/batch/disable-unhealthy", json={"provider_ids": [unhealthy["id"]]})
    assert disabled.json()["count"] == 1
    assert temp_store.provider(unhealthy["id"])["enabled"] is False
    assert temp_store.provider(healthy["id"])["enabled"] is True

    deleted = client.post("/api/providers/batch/delete-unhealthy", json={"provider_ids": [unhealthy["id"]]})
    assert deleted.json()["count"] == 1
    assert temp_store.provider(unhealthy["id"]) is None


def test_provider_health_history_keeps_recent_check_and_call_states(tmp_path):
    store = Store(tmp_path / "router.db")
    provider = store.create_provider({"name": "Route", "kind": "deeplx", "endpoint": "https://route.example", "api_key": "", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    store.set_health(provider["id"], "healthy", 90, source="call")
    store.set_health(provider["id"], "unhealthy", 120, "timeout", source="check")
    history = store.providers()[0]["health_history"]
    assert [item["status"] for item in history] == ["unhealthy", "healthy"]
    assert [item["source"] for item in history] == ["check", "call"]
