import sqlite3

from deepl_router.store import Store
from deepl_router.upstreams import quota_exceeded


def test_quota_exceeded_characters_remote_limit():
    assert quota_exceeded({"quota": {"type": "characters", "used": 500000, "limit": 500000}, "quota_limit": None}) is True
    assert quota_exceeded({"quota": {"type": "characters", "used": 499999, "limit": 500000}, "quota_limit": None}) is False


def test_quota_exceeded_characters_user_limit_takes_min():
    provider = {"quota": {"type": "characters", "used": 300000, "limit": 500000}, "quota_limit": 200000}
    assert quota_exceeded(provider) is True
    provider["quota_limit"] = 400000
    assert quota_exceeded(provider) is False


def test_quota_exceeded_characters_no_limits():
    assert quota_exceeded({"quota": {"type": "characters", "used": 100, "limit": None}, "quota_limit": None}) is False
    assert quota_exceeded({"quota": {"type": "characters", "used": 100, "limit": 0}, "quota_limit": None}) is False


def test_quota_exceeded_balance_threshold():
    assert quota_exceeded({"quota": {"type": "balance", "amount": 5.0, "currency": "CNY"}, "quota_limit": 10.0}) is True
    assert quota_exceeded({"quota": {"type": "balance", "amount": 15.0, "currency": "CNY"}, "quota_limit": 10.0}) is False
    assert quota_exceeded({"quota": {"type": "balance", "amount": 5.0, "currency": "CNY"}, "quota_limit": None}) is False


def test_quota_exceeded_defensive():
    assert quota_exceeded({"quota": None, "quota_limit": 10}) is False
    assert quota_exceeded({}) is False
    assert quota_exceeded({"quota": "not-json{", "quota_limit": 10}) is False
    assert quota_exceeded({"quota": {"type": "unknown"}}) is False


def test_store_migrates_legacy_usage_columns_to_quota(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('deepl', 'deeplx', 'tencent', 'custom')),
            endpoint TEXT NOT NULL, api_key TEXT NOT NULL DEFAULT '', api_secret TEXT NOT NULL DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 100, weight INTEGER NOT NULL DEFAULT 1,
            enabled INTEGER NOT NULL DEFAULT 1, timeout_seconds INTEGER NOT NULL DEFAULT 20,
            last_status TEXT NOT NULL DEFAULT 'unknown', last_latency_ms INTEGER, last_error TEXT,
            usage_character_count INTEGER, usage_character_limit INTEGER, usage_checked_at TEXT, usage_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute(
            "INSERT INTO providers (name, kind, endpoint, api_key, usage_character_count, usage_character_limit, usage_checked_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Official", "deepl", "https://api.deepl.com", "key", 120, 500000, "2026-01-01 00:00:00"),
        )
    store = Store(path)
    provider = store.providers()[0]
    assert provider["quota"] == {"type": "characters", "used": 120, "limit": 500000}
    assert provider["quota_checked_at"] == "2026-01-01 00:00:00"
    # CHECK 约束已移除，可插入新 kind
    created = store.create_provider({"name": "Volc", "kind": "volcengine", "endpoint": "https://translate.volcengineapi.com", "api_key": "ak", "api_secret": "sk", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20})
    assert created["kind"] == "volcengine"
    with sqlite3.connect(path) as conn:
        definition = conn.execute("SELECT sql FROM sqlite_master WHERE name='providers'").fetchone()[0]
    assert "CHECK(" not in definition.upper().replace(" ", "")


def test_store_set_quota_and_exceeded_flag(tmp_path):
    store = Store(tmp_path / "router.db")
    provider = store.create_provider({"name": "Volc", "kind": "volcengine", "endpoint": "https://translate.volcengineapi.com", "api_key": "ak", "api_secret": "sk", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20, "quota_limit": 10.0})
    assert provider["quota_exceeded"] is False
    store.set_quota(provider["id"], {"type": "balance", "amount": 5.0, "currency": "CNY"})
    saved = store.provider(provider["id"], reveal_key=False)
    assert saved["quota"] == {"type": "balance", "amount": 5.0, "currency": "CNY"}
    assert saved["quota_exceeded"] is True


def test_update_provider_can_clear_quota_limit(tmp_path):
    store = Store(tmp_path / "router.db")
    provider = store.create_provider({"name": "Volc", "kind": "volcengine", "endpoint": "https://translate.volcengineapi.com", "api_key": "ak", "api_secret": "sk", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20, "quota_limit": 10.0})
    updated = store.update_provider(provider["id"], {"quota_limit": None})
    assert updated["quota_limit"] is None
