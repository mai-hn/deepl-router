from fastapi.testclient import TestClient

import deepl_router.app as application
from deepl_router.store import Store


def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(application, "store", Store(tmp_path / "router.db"))
    return TestClient(application.app)


def test_upstream_kinds_lists_all_seven(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.get("/api/upstream-kinds")
    assert response.status_code == 200
    kinds = {item["kind"]: item for item in response.json()}
    assert set(kinds) == {"deepl", "deeplx", "tencent", "volcengine", "azure", "baidu", "custom"}
    assert kinds["azure"]["needs_region"] is True
    assert kinds["azure"]["quota_type"] is None
    assert kinds["baidu"]["quota_type"] is None
    assert kinds["baidu"]["needs_secret"] is True
    assert kinds["deepl"]["quota_type"] == "characters"
    assert kinds["volcengine"]["quota_type"] == "balance"
    assert kinds["tencent"]["quota_type"] == "balance"
    for meta in kinds.values():
        assert meta["label"]
        assert meta["color"].startswith("#")


def test_create_provider_rejects_unknown_kind(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.post("/api/providers", json={"name": "X", "kind": "nope", "endpoint": "https://example.com"})
    assert response.status_code == 422


def test_create_azure_provider_with_region(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.post("/api/providers", json={"name": "Azure", "kind": "azure", "endpoint": "https://api.cognitive.microsofttranslator.com", "api_key": "k", "region": "eastasia"})
    assert response.status_code == 201
    assert response.json()["region"] == "eastasia"


def test_quota_limit_rejected_for_unsupported_kind(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.post("/api/providers", json={"name": "DLX", "kind": "deeplx", "endpoint": "https://dlx.example.com", "quota_limit": 100})
    assert response.status_code == 422
    assert "不支持" in response.json()["detail"]


def test_quota_limit_accepted_for_balance_kind_and_patch_clears_it(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    created = client.post("/api/providers", json={"name": "Volc", "kind": "volcengine", "endpoint": "https://translate.volcengineapi.com", "api_key": "ak", "api_secret": "sk", "quota_limit": 10.5})
    assert created.status_code == 201
    assert created.json()["quota_limit"] == 10.5
    provider_id = created.json()["id"]
    patched = client.patch(f"/api/providers/{provider_id}", json={"quota_limit": None})
    assert patched.status_code == 200
    assert patched.json()["quota_limit"] is None


def test_quota_endpoint_rejects_unsupported_kind(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    created = client.post("/api/providers", json={"name": "DLX", "kind": "deeplx", "endpoint": "https://dlx.example.com"})
    response = client.post(f"/api/providers/{created.json()['id']}/quota")
    assert response.status_code == 422


def test_dashboard_stats(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    client.post("/api/providers", json={"name": "DLX", "kind": "deeplx", "endpoint": "https://dlx.example.com"})
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["providers"]["total"] == 1
    assert body["providers"]["enabled"] == 1
    assert body["requests"]["total"] == 0
