from fastapi.testclient import TestClient

import deepl_router.app as application
from deepl_router.router import TranslationResult
from deepl_router.store import Store


def use_temp_store(tmp_path, monkeypatch):
    temp_store = Store(tmp_path / "router.db")
    monkeypatch.setattr(application, "store", temp_store)
    return temp_store


def test_deepl_json_downstream_shape(tmp_path, monkeypatch):
    use_temp_store(tmp_path, monkeypatch)

    async def fake_translate(text, target_lang, source_lang):
        return TranslationResult("你好", "EN", "mock")

    monkeypatch.setattr(application.router, "translate", fake_translate)
    client = TestClient(application.app)
    response = client.post("/v2/translate", json={"text": ["hello"], "target_lang": "ZH"})
    assert response.status_code == 200
    assert response.json()["translations"][0]["text"] == "你好"


def test_immersive_translate_text_list(tmp_path, monkeypatch):
    use_temp_store(tmp_path, monkeypatch)

    async def fake_translate(text, target_lang, source_lang):
        return TranslationResult(f"译文:{text}", "EN", "mock")

    monkeypatch.setattr(application.router, "translate", fake_translate)
    client = TestClient(application.app)
    response = client.post("/translate", json={"source_lang": "en", "target_lang": "zh", "text_list": ["one", "two"]})
    assert response.status_code == 200
    assert [item["text"] for item in response.json()["translations"]] == ["译文:one", "译文:two"]


def test_downstream_key_can_be_cleared(tmp_path, monkeypatch):
    temp_store = use_temp_store(tmp_path, monkeypatch)
    client = TestClient(application.app)
    response = client.put("/api/settings", json={"downstream_key": ""})
    assert response.status_code == 200
    assert temp_store.settings()["downstream_key"] == ""


def test_immersive_language_codes_are_normalized(tmp_path, monkeypatch):
    use_temp_store(tmp_path, monkeypatch)
    seen = {}

    async def fake_translate(text, target_lang, source_lang):
        seen.update(target_lang=target_lang, source_lang=source_lang)
        return TranslationResult("你好", "EN", "mock")

    monkeypatch.setattr(application.router, "translate", fake_translate)
    client = TestClient(application.app)
    response = client.post("/translate", json={"source_lang": "auto", "target_lang": "zh-CN", "text_list": ["hello"]})
    assert response.status_code == 200
    assert seen == {"target_lang": "ZH", "source_lang": None}
