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
