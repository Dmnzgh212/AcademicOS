from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class SourceHealth:
    source_key: str
    status: str
    last_attempt_at: str
    last_success_at: str | None
    last_error: str | None
    consecutive_failures: int
    items_changed: int
    items_unchanged: int
    downloaded_files: int
    metadata: dict[str, Any]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def mark_success(
    conn: sqlite3.Connection,
    source_key: str,
    *,
    changed: int = 0,
    unchanged: int = 0,
    downloaded_files: int = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    now = _now()
    with conn:
        conn.execute(
            """
            INSERT INTO source_health(
                source_key, status, last_attempt_at, last_success_at, last_error,
                consecutive_failures, items_changed, items_unchanged,
                downloaded_files, metadata_json
            ) VALUES (?, 'ok', ?, ?, NULL, 0, ?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                status='ok',
                last_attempt_at=excluded.last_attempt_at,
                last_success_at=excluded.last_success_at,
                last_error=NULL,
                consecutive_failures=0,
                items_changed=excluded.items_changed,
                items_unchanged=excluded.items_unchanged,
                downloaded_files=excluded.downloaded_files,
                metadata_json=excluded.metadata_json
            """,
            (
                source_key,
                now,
                now,
                max(0, changed),
                max(0, unchanged),
                max(0, downloaded_files),
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            ),
        )


def mark_failure(
    conn: sqlite3.Connection,
    source_key: str,
    error: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    now = _now()
    with conn:
        conn.execute(
            """
            INSERT INTO source_health(
                source_key, status, last_attempt_at, last_success_at, last_error,
                consecutive_failures, items_changed, items_unchanged,
                downloaded_files, metadata_json
            ) VALUES (?, 'error', ?, NULL, ?, 1, 0, 0, 0, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                status='error',
                last_attempt_at=excluded.last_attempt_at,
                last_error=excluded.last_error,
                consecutive_failures=source_health.consecutive_failures + 1,
                metadata_json=excluded.metadata_json
            """,
            (
                source_key,
                now,
                error[:4000],
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            ),
        )


def list_health(conn: sqlite3.Connection) -> list[SourceHealth]:
    rows = conn.execute(
        "SELECT * FROM source_health ORDER BY status DESC, source_key"
    ).fetchall()
    result: list[SourceHealth] = []
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        result.append(
            SourceHealth(
                source_key=row["source_key"],
                status=row["status"],
                last_attempt_at=row["last_attempt_at"],
                last_success_at=row["last_success_at"],
                last_error=row["last_error"],
                consecutive_failures=row["consecutive_failures"],
                items_changed=row["items_changed"],
                items_unchanged=row["items_unchanged"],
                downloaded_files=row["downloaded_files"],
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        )
    return result
