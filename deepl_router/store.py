from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS providers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('deepl', 'deeplx', 'custom')),
  endpoint TEXT NOT NULL,
  api_key TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 100,
  weight INTEGER NOT NULL DEFAULT 1,
  enabled INTEGER NOT NULL DEFAULT 1,
  timeout_seconds INTEGER NOT NULL DEFAULT 20,
  last_status TEXT NOT NULL DEFAULT 'unknown',
  last_latency_ms INTEGER,
  last_error TEXT,
  usage_character_count INTEGER,
  usage_character_limit INTEGER,
  usage_checked_at TEXT,
  usage_error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS request_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  route TEXT NOT NULL,
  downstream_request TEXT NOT NULL,
  upstream_attempts TEXT NOT NULL DEFAULT '[]',
  response_body TEXT,
  provider TEXT,
  status TEXT NOT NULL,
  latency_ms INTEGER,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs(created_at DESC);
"""


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(SCHEMA)
            self._ensure_provider_usage_columns(conn)
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('routing_mode', 'weighted')")
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('fallback_enabled', 'true')")
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('downstream_key', '')")

    @staticmethod
    def _ensure_provider_usage_columns(conn: sqlite3.Connection) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(providers)").fetchall()}
        for name, definition in {
            "usage_character_count": "INTEGER",
            "usage_character_limit": "INTEGER",
            "usage_checked_at": "TEXT",
            "usage_error": "TEXT",
        }.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE providers ADD COLUMN {name} {definition}")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def row_to_dict(row: sqlite3.Row, reveal_key: bool = False) -> dict[str, Any]:
        item = dict(row)
        item["enabled"] = bool(item["enabled"])
        if not reveal_key:
            key = item.pop("api_key", "")
            item["key_hint"] = ("•" * 8 + key[-4:]) if key else "未设置"
        return item

    def providers(self, reveal_key: bool = False) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM providers ORDER BY priority ASC, id ASC").fetchall()
        return [self.row_to_dict(row, reveal_key) for row in rows]

    def provider(self, provider_id: int, reveal_key: bool = True) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
        return self.row_to_dict(row, reveal_key) if row else None

    def create_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        fields = ("name", "kind", "endpoint", "api_key", "priority", "weight", "enabled", "timeout_seconds")
        with self.connection() as conn:
            cursor = conn.execute(
                f"INSERT INTO providers ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                [payload[field] for field in fields],
            )
            row = conn.execute("SELECT * FROM providers WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self.row_to_dict(row)

    def create_providers(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fields = ("name", "kind", "endpoint", "api_key", "priority", "weight", "enabled", "timeout_seconds")
        with self.connection() as conn:
            ids = []
            for payload in payloads:
                cursor = conn.execute(
                    f"INSERT INTO providers ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                    [payload[field] for field in fields],
                )
                ids.append(cursor.lastrowid)
            rows = conn.execute(
                f"SELECT * FROM providers WHERE id IN ({','.join('?' for _ in ids)}) ORDER BY id ASC", ids
            ).fetchall()
        return [self.row_to_dict(row) for row in rows]

    def update_provider(self, provider_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"name", "kind", "endpoint", "api_key", "priority", "weight", "enabled", "timeout_seconds"}
        changes = {key: value for key, value in payload.items() if key in allowed and value is not None}
        if not changes:
            return self.provider(provider_id, reveal_key=False)
        assignments = ", ".join(f"{key} = ?" for key in changes)
        with self.connection() as conn:
            conn.execute(f"UPDATE providers SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (*changes.values(), provider_id))
            row = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
        return self.row_to_dict(row) if row else None

    def delete_provider(self, provider_id: int) -> bool:
        with self.connection() as conn:
            return conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,)).rowcount > 0

    def set_health(self, provider_id: int, status: str, latency_ms: int | None, error: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute("UPDATE providers SET last_status = ?, last_latency_ms = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, latency_ms, error, provider_id))

    def set_usage(self, provider_id: int, character_count: int | None, character_limit: int | None, error: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute(
                """UPDATE providers SET usage_character_count = ?, usage_character_limit = ?,
                   usage_checked_at = CURRENT_TIMESTAMP, usage_error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (character_count, character_limit, error, provider_id),
            )

    def settings(self) -> dict[str, str]:
        with self.connection() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def update_settings(self, values: dict[str, Any]) -> dict[str, str]:
        allowed = {"routing_mode", "fallback_enabled", "downstream_key"}
        with self.connection() as conn:
            for key, value in values.items():
                if key in allowed and value is not None:
                    conn.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
        return self.settings()

    def create_request_log(self, *, request_id: str, route: str, downstream_request: dict[str, Any], upstream_attempts: list[dict[str, Any]], response_body: dict[str, Any] | None, provider: str | None, status: str, latency_ms: int | None, error: str | None = None) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO request_logs(request_id, route, downstream_request, upstream_attempts, response_body, provider, status, latency_ms, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (request_id, route, json.dumps(downstream_request, ensure_ascii=False), json.dumps(upstream_attempts, ensure_ascii=False), json.dumps(response_body, ensure_ascii=False) if response_body is not None else None, provider, status, latency_ms, error),
            )
        return int(cursor.lastrowid)

    @staticmethod
    def log_row_to_dict(row: sqlite3.Row, detail: bool = False) -> dict[str, Any]:
        item = dict(row)
        for field in ("downstream_request", "upstream_attempts", "response_body"):
            if item[field] is not None:
                item[field] = json.loads(item[field])
        if not detail:
            request = item.pop("downstream_request")
            item.pop("upstream_attempts", None)
            item.pop("response_body", None)
            item["text_preview"] = str(request.get("text", ""))[:100]
            item["attempt_count"] = len(json.loads(row["upstream_attempts"]))
        return item

    def request_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM request_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self.log_row_to_dict(row) for row in rows]

    def request_log(self, log_id: int) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM request_logs WHERE id = ?", (log_id,)).fetchone()
        return self.log_row_to_dict(row, detail=True) if row else None
