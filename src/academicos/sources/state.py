from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any


def get_sync_state(conn: sqlite3.Connection, source_key: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT source_key, cursor, last_success_at, metadata_json FROM sync_state WHERE source_key = ?",
        (source_key,),
    ).fetchone()
    if row is None:
        return None
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "source_key": row["source_key"],
        "cursor": row["cursor"],
        "last_success_at": row["last_success_at"],
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def get_cursor(conn: sqlite3.Connection, source_key: str) -> str | None:
    state = get_sync_state(conn, source_key)
    return state["cursor"] if state else None


def set_sync_state(
    conn: sqlite3.Connection,
    source_key: str,
    *,
    cursor: str | None,
    metadata: dict[str, Any] | None = None,
    success_at: datetime | None = None,
) -> None:
    timestamp = (success_at or datetime.now(UTC)).isoformat()
    payload = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
    with conn:
        conn.execute(
            """
            INSERT INTO sync_state(source_key, cursor, last_success_at, metadata_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                cursor = excluded.cursor,
                last_success_at = excluded.last_success_at,
                metadata_json = excluded.metadata_json
            """,
            (source_key, cursor, timestamp, payload),
        )
