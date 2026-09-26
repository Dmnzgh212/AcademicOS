from __future__ import annotations

import hashlib
import json
import sqlite3
from uuid import UUID, uuid5

from academicos.calendar.models import Evidence, SourceItem, SourceType

SOURCE_NAMESPACE = UUID("cdbd10ea-c3f0-4dde-943f-81770e6d22fc")


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_item_id(source_type: SourceType, source_id: str) -> str:
    return str(uuid5(SOURCE_NAMESPACE, f"source|{source_type.value}|{source_id}"))


def evidence_id(source_item: str, field_path: str) -> str:
    return str(uuid5(SOURCE_NAMESPACE, f"evidence|{source_item}|{field_path}"))


def upsert_source_item(conn: sqlite3.Connection, item: SourceItem) -> bool:
    """Persist a source item and return True when content is new or changed."""
    existing = conn.execute(
        "SELECT content_hash FROM source_items WHERE id = ?",
        (item.id,),
    ).fetchone()
    changed = existing is None or existing["content_hash"] != item.content_hash

    with conn:
        conn.execute(
            """
            INSERT INTO source_items(
                id, source_type, source_id, course_id, source_url,
                source_timestamp, fetched_at, content_hash, raw_text, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                course_id=excluded.course_id,
                source_url=excluded.source_url,
                source_timestamp=excluded.source_timestamp,
                fetched_at=excluded.fetched_at,
                content_hash=excluded.content_hash,
                raw_text=excluded.raw_text,
                raw_json=excluded.raw_json
            """,
            (
                item.id,
                item.source_type.value,
                item.source_id,
                item.course_id,
                item.source_url,
                item.source_timestamp.isoformat() if item.source_timestamp else None,
                item.fetched_at.isoformat(),
                item.content_hash,
                item.raw_text,
                json.dumps(item.raw_json, ensure_ascii=False, sort_keys=True)
                if item.raw_json is not None
                else None,
            ),
        )
    return changed


def upsert_evidence(conn: sqlite3.Connection, evidence: Evidence) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO evidence(id, source_item_id, excerpt, field_path)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                excerpt=excluded.excerpt,
                field_path=excluded.field_path
            """,
            (evidence.id, evidence.source_item_id, evidence.excerpt, evidence.field_path),
        )


def delete_pending_candidates_for_source(
    conn: sqlite3.Connection,
    source_item: str,
) -> int:
    """Drop stale pending candidates while preserving a valid supersession chain."""
    rows = conn.execute(
        """
        SELECT DISTINCT ce.id
        FROM candidate_events AS ce
        JOIN candidate_evidence AS link ON link.candidate_event_id = ce.id
        JOIN evidence AS e ON e.id = link.evidence_id
        WHERE e.source_item_id = ? AND ce.status = 'pending'
        """,
        (source_item,),
    ).fetchall()
    ids = [row["id"] for row in rows]
    if not ids:
        return 0

    with conn:
        for candidate_id in ids:
            conn.execute(
                """
                UPDATE candidate_events
                SET status = 'pending',
                    superseded_by_candidate_id = NULL,
                    superseded_at = NULL
                WHERE status = 'superseded'
                  AND superseded_by_candidate_id = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM task_deadline_changes AS tdc
                      WHERE tdc.candidate_event_id = candidate_events.id
                  )
                """,
                (candidate_id,),
            )
        conn.executemany(
            "DELETE FROM candidate_events WHERE id = ?",
            [(candidate_id,) for candidate_id in ids],
        )
    return len(ids)
