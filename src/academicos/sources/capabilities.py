from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

import requests


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def response_shape(payload: object) -> dict[str, Any]:
    """Return a value-free structural summary safe for diagnostic reports."""
    if isinstance(payload, list):
        keys: set[str] = set()
        for item in payload[:10]:
            if isinstance(item, dict):
                keys.update(str(key) for key in item.keys())
        return {
            "kind": "list",
            "count": len(payload),
            "item_keys": sorted(keys)[:80],
        }
    if isinstance(payload, dict):
        return {
            "kind": "dict",
            "keys": sorted(str(key) for key in payload.keys())[:120],
        }
    if payload is None:
        return {"kind": "null"}
    return {"kind": type(payload).__name__}


def record_success(
    conn: sqlite3.Connection,
    source_key: str,
    endpoint: str,
    payload: object,
    *,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(UTC)
    conn.execute(
        """
        INSERT INTO endpoint_capabilities(
            source_key, endpoint, status, http_status, last_checked_at,
            next_probe_at, response_shape_json, last_error
        ) VALUES (?, ?, 'supported', 200, ?, NULL, ?, NULL)
        ON CONFLICT(source_key, endpoint) DO UPDATE SET
            status='supported',
            http_status=200,
            last_checked_at=excluded.last_checked_at,
            next_probe_at=NULL,
            response_shape_json=excluded.response_shape_json,
            last_error=NULL
        """,
        (source_key, endpoint, _iso(now), json.dumps(response_shape(payload), sort_keys=True)),
    )
    conn.commit()


def _classification(status_code: int | None) -> tuple[str, timedelta | None]:
    if status_code in (404, 405):
        return "unsupported", timedelta(days=30)
    if status_code == 403:
        return "forbidden", timedelta(hours=12)
    if status_code == 401:
        return "auth_error", None
    if status_code == 429 or (status_code is not None and 500 <= status_code <= 599):
        return "transient", timedelta(minutes=10)
    return "error", timedelta(hours=1)


def record_failure(
    conn: sqlite3.Connection,
    source_key: str,
    endpoint: str,
    error: Exception,
    *,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(UTC)
    status_code: int | None = None
    if isinstance(error, requests.HTTPError) and error.response is not None:
        status_code = error.response.status_code
    status, delay = _classification(status_code)
    next_probe = _iso(now + delay) if delay is not None else None
    message = f"{type(error).__name__}: {error}"
    conn.execute(
        """
        INSERT INTO endpoint_capabilities(
            source_key, endpoint, status, http_status, last_checked_at,
            next_probe_at, response_shape_json, last_error
        ) VALUES (?, ?, ?, ?, ?, ?, '{}', ?)
        ON CONFLICT(source_key, endpoint) DO UPDATE SET
            status=excluded.status,
            http_status=excluded.http_status,
            last_checked_at=excluded.last_checked_at,
            next_probe_at=excluded.next_probe_at,
            last_error=excluded.last_error
        """,
        (source_key, endpoint, status, status_code, _iso(now), next_probe, message[:1000]),
    )
    conn.commit()


def should_probe(
    conn: sqlite3.Connection,
    source_key: str,
    endpoint: str,
    *,
    now: datetime | None = None,
) -> bool:
    row = conn.execute(
        "SELECT status, next_probe_at FROM endpoint_capabilities WHERE source_key=? AND endpoint=?",
        (source_key, endpoint),
    ).fetchone()
    if row is None:
        return True
    if row["status"] in {"supported", "auth_error"}:
        return True
    next_probe = row["next_probe_at"]
    if not next_probe:
        return True
    try:
        due = datetime.fromisoformat(str(next_probe).replace("Z", "+00:00"))
    except ValueError:
        return True
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return (now or datetime.now(UTC)) >= due


def capability_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT source_key, endpoint, status, http_status, last_checked_at,
               next_probe_at, response_shape_json, last_error
        FROM endpoint_capabilities
        ORDER BY source_key, endpoint
        """
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        try:
            shape = json.loads(row["response_shape_json"] or "{}")
        except json.JSONDecodeError:
            shape = {}
        result.append(
            {
                "source_key": row["source_key"],
                "endpoint": row["endpoint"],
                "status": row["status"],
                "http_status": row["http_status"],
                "last_checked_at": row["last_checked_at"],
                "next_probe_at": row["next_probe_at"],
                "response_shape": shape,
                "last_error": row["last_error"],
            }
        )
    return result
