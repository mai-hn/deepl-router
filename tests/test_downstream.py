from fastapi.testclient import TestClient

import deepl_router.app as application
from deepl_router.router import TranslationResult


def test_deepl_json_downstream_shape(monkeypatch):
    async def fake_translate(text, target_lang, source_lang):
        return TranslationResult("你好", "EN", "mock")

    monkeypatch.setattr(application.router, "translate", fake_translate)
    monkeypatch.setattr(application.store, "settings", lambda: {"downstream_key": ""})
    client = TestClient(application.app)
    response = client.post("/v2/translate", json={"text": ["hello"], "target_lang": "ZH"})
    assert response.status_code == 200
    assert response.json()["translations"][0]["text"] == "你好"


def test_immersive_translate_text_list(monkeypatch):
    async def fake_translate(text, target_lang, source_lang):
        return TranslationResult(f"译文:{text}", "EN", "mock")

    monkeypatch.setattr(application.router, "translate", fake_translate)
    monkeypatch.setattr(application.store, "settings", lambda: {"downstream_key": ""})
    client = TestClient(application.app)
    response = client.post("/translate", json={"source_lang": "en", "target_lang": "zh", "text_list": ["one", "two"]})
    assert response.status_code == 200
    assert [item["text"] for item in response.json()["translations"]] == ["译文:one", "译文:two"]
