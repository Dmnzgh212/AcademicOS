from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from academicos.calendar.models import CandidateStatus, EventKind


@dataclass(frozen=True)
class CandidateInboxItem:
    id: str
    kind: EventKind
    status: CandidateStatus
    confidence: float
    course_code: str | None
    course_section: str | None
    target_ref: str | None
    effective_at: datetime | None
    created_at: datetime
    title: str
    excerpt: str
    payload: dict


def list_candidate_inbox(
    conn: sqlite3.Connection,
    *,
    status: CandidateStatus | None = CandidateStatus.PENDING,
    limit: int = 100,
) -> list[CandidateInboxItem]:
    params: list[object] = []
    status_clause = ""
    if status is not None:
        status_clause = "WHERE ce.status = ?"
        params.append(status.value)
    params.append(limit)

    rows = conn.execute(
        f"""
        SELECT
            ce.*,
            c.code AS course_code,
            c.section AS course_section,
            e.excerpt AS evidence_excerpt,
            si.raw_text AS source_text
        FROM candidate_events AS ce
        LEFT JOIN courses AS c ON c.id = ce.course_id
        LEFT JOIN evidence AS e ON e.id = (
            SELECT link.evidence_id
            FROM candidate_evidence AS link
            WHERE link.candidate_event_id = ce.id
            ORDER BY link.evidence_id
            LIMIT 1
        )
        LEFT JOIN source_items AS si ON si.id = e.source_item_id
        {status_clause}
        ORDER BY ce.confidence DESC, ce.created_at DESC
        LIMIT ?
        """,
        params,
    ).fetchall()

    items: list[CandidateInboxItem] = []
    for row in rows:
        source_text = row["source_text"] or ""
        title = source_text.splitlines()[0].strip() if source_text else row["kind"]
        excerpt = (row["evidence_excerpt"] or source_text).strip()
        items.append(
            CandidateInboxItem(
                id=row["id"],
                kind=EventKind(row["kind"]),
                status=CandidateStatus(row["status"]),
                confidence=float(row["confidence"]),
                course_code=row["course_code"],
                course_section=row["course_section"],
                target_ref=row["target_ref"],
                effective_at=datetime.fromisoformat(row["effective_at"])
                if row["effective_at"]
                else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                title=title,
                excerpt=excerpt,
                payload=json.loads(row["payload_json"] or "{}"),
            )
        )
    return items
