from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import JSONResponse
from flask import Flask, send_from_directory
from pydantic import BaseModel, Field

from .router import ProviderRouter, TranslationError
from .store import Store

BASE_DIR = Path(__file__).resolve().parent.parent
store = Store(os.getenv("DEEPL_ROUTER_DB", str(BASE_DIR / "data" / "router.db")))
router = ProviderRouter(store)


class ProviderInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["deepl", "deeplx", "custom"]
    endpoint: str = Field(min_length=8, max_length=500)
    api_key: str = Field(default="", max_length=500)
    priority: int = Field(default=100, ge=1, le=10000)
    weight: int = Field(default=1, ge=1, le=1000)
    enabled: bool = True
    timeout_seconds: int = Field(default=20, ge=2, le=120)


class ProviderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: Literal["deepl", "deeplx", "custom"] | None = None
    endpoint: str | None = Field(default=None, min_length=8, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    priority: int | None = Field(default=None, ge=1, le=10000)
    weight: int | None = Field(default=None, ge=1, le=1000)
    enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=2, le=120)


class SettingsInput(BaseModel):
    routing_mode: Literal["weighted"] | None = None
    fallback_enabled: bool | None = None
    downstream_key: str | None = Field(default=None, max_length=500)


class TranslateInput(BaseModel):
    text: str | list[str] | None = None
    text_list: list[str] | None = None
    target_lang: str
    source_lang: str | None = None


def flask_app() -> Flask:
    application = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/static")

    @application.get("/")
    def dashboard():
        return send_from_directory(BASE_DIR / "static", "index.html")

    return application


app = FastAPI(title="DeepRouter", version="0.1.0")


def require_downstream_key(authorization: str | None = Header(default=None)) -> None:
    configured_key = store.settings().get("downstream_key", "")
    if not configured_key:
        return
    provided = authorization.removeprefix("DeepL-Auth-Key ").removeprefix("Bearer ") if authorization else ""
    if provided != configured_key:
        raise HTTPException(status_code=403, detail="无效的下游访问密钥")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/providers")
def list_providers():
    return store.providers()


@app.post("/api/providers", status_code=201)
def create_provider(payload: ProviderInput):
    return store.create_provider(payload.model_dump())


@app.patch("/api/providers/{provider_id}")
def update_provider(provider_id: int, payload: ProviderPatch):
    item = store.update_provider(provider_id, payload.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=404, detail="通道不存在")
    return item


@app.delete("/api/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: int):
    if not store.delete_provider(provider_id):
        raise HTTPException(status_code=404, detail="通道不存在")


@app.post("/api/providers/{provider_id}/check")
async def check_provider(provider_id: int):
    provider = store.provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="通道不存在")
    return await router.check(provider)


@app.get("/api/settings")
def get_settings():
    values = store.settings()
    return {**values, "fallback_enabled": values.get("fallback_enabled") == "true", "downstream_key_hint": "已设置" if values.get("downstream_key") else "未设置", "downstream_key": ""}


@app.put("/api/settings")
def update_settings(payload: SettingsInput):
    values = payload.model_dump(exclude_unset=True)
    if "fallback_enabled" in values:
        values["fallback_enabled"] = str(values["fallback_enabled"]).lower()
    store.update_settings(values)
    return get_settings()


async def run_translation(text: str, target_lang: str, source_lang: str | None):
    try:
        result = await router.translate(text, target_lang.upper(), source_lang.upper() if source_lang else None)
        return {"translations": [{"text": result.text, "detected_source_language": result.detected_source_language}], "provider": result.provider}
    except TranslationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/translate")
async def translate_json(payload: TranslateInput, _: None = Depends(require_downstream_key)):
    # Immersive Translate custom interface: {source_lang, target_lang, text_list}.
    texts = payload.text_list or ([payload.text] if isinstance(payload.text, str) else payload.text)
    if not texts:
        raise HTTPException(status_code=422, detail="text 或 text_list 不能为空")
    results = [await run_translation(text, payload.target_lang, payload.source_lang) for text in texts]
    translations = [
        {
            "text": result["translations"][0]["text"],
            "detected_source_lang": result["translations"][0]["detected_source_language"],
        }
        for result in results
    ]
    return {
        "data": translations[0]["text"] if len(translations) == 1 else [item["text"] for item in translations],
        "translations": translations,
        "providers": [r["provider"] for r in results],
    }


@app.post("/v2/translate")
async def translate_deepl(request: Request, authorization: str | None = Header(default=None)):
    """DeepL-compatible endpoint supporting the official JSON and form payloads."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        text = payload.get("text", [])
        target_lang = payload.get("target_lang")
        source_lang = payload.get("source_lang")
        auth_key = payload.get("auth_key")
    else:
        payload = await request.form()
        text = payload.getlist("text")
        target_lang = payload.get("target_lang")
        source_lang = payload.get("source_lang")
        auth_key = payload.get("auth_key")
    text = [text] if isinstance(text, str) else text
    if not text or not target_lang:
        raise HTTPException(status_code=422, detail="text 和 target_lang 为必填项")
    configured_key = store.settings().get("downstream_key", "")
    provided = authorization.removeprefix("DeepL-Auth-Key ").removeprefix("Bearer ") if authorization else auth_key or ""
    if configured_key and provided != configured_key:
        raise HTTPException(status_code=403, detail="无效的下游访问密钥")
    results = [await run_translation(item, target_lang, source_lang) for item in text]
    return {"translations": [item["translations"][0] for item in results]}


@app.get("/v2/usage")
def usage(_: None = Depends(require_downstream_key)):
    return {"character_count": 0, "character_limit": 0, "router": "DeepRouter"}


@app.exception_handler(TranslationError)
async def translation_error_handler(_, exc: TranslationError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


app.mount("/", WSGIMiddleware(flask_app()))
