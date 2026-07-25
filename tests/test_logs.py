from fastapi.testclient import TestClient

import deepl_router.app as application
from deepl_router.router import TranslationResult
from deepl_router.store import Store


def test_translation_creates_inspectable_log(tmp_path, monkeypatch):
    temp_store = Store(tmp_path / "router.db")

    async def fake_translate(text, target_lang, source_lang):
        return TranslationResult(
            "你好", "EN", "Mock route",
            {"method": "POST", "endpoint": "https://upstream.example/translate", "body": {"text": text}},
            {"status_code": 200, "body": {"text": "你好"}},
            [],
        )

    monkeypatch.setattr(application, "store", temp_store)
    monkeypatch.setattr(application.router, "translate", fake_translate)
    client = TestClient(application.app)
    response = client.post("/translate", json={"text": "hello", "target_lang": "zh-CN", "source_lang": "auto"})
    assert response.status_code == 200

    logs = client.get("/api/logs").json()
    assert logs[0]["status"] == "success"
    assert logs[0]["text_preview"] == "hello"

    detail = client.get(f"/api/logs/{logs[0]['id']}").json()
    assert detail["upstream_attempts"][0]["request"]["endpoint"] == "https://upstream.example/translate"
    assert "Authorization" not in str(detail)
