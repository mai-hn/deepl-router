# DeepRouter

自托管的 DeepL / DeepLX 翻译路由服务。提供管理台、加权轮询、按优先级回退、通道健康检查以及 DeepL 兼容的下游接口。

## 启动

```powershell
uv sync --extra dev
uv run uvicorn deepl_router.app:app --host 127.0.0.1 --port 8080 --reload
```

打开 `http://127.0.0.1:8080`。首次运行会在项目目录创建 `data/router.db`。

## 下游接口

- `POST /v2/translate` — DeepL 兼容，接受官方 JSON 或表单请求。鉴权使用 `Authorization: DeepL-Auth-Key <下游访问密钥>`，或 `auth_key` 字段。
- `POST /translate` — JSON 接口，也兼容沉浸式翻译格式：`{"source_lang":"en","target_lang":"zh","text_list":["Hello"]}`。
- `GET /v2/usage` — 返回路由服务状态。

在管理台「路由策略」中设置下游访问密钥。空密钥仅适合本机开发，生产环境必须设置。

## 上游类型

- **DeepL API**：填入官方 API Key；免费 Key 会自动使用 `api-free.deepl.com`。
- **DeepLX / DLX**：填入 DLX 服务地址；可选 Key 作为 `Authorization` Bearer Token 发送。
- **自定义 API**：填入一个兼容 `/translate` JSON 协议的地址与可选 Bearer Key。

> 管理台展示 Key 的掩码；数据库内配置应放在受限磁盘或卷中。此示例未内置密钥管理服务。
