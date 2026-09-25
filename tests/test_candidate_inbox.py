from __future__ import annotations

from datetime import datetime, UTC

from academicos.calendar.events import persist_candidate_event
from academicos.calendar.inbox import list_candidate_inbox
from academicos.calendar.models import CandidateEvent, CandidateStatus, EventKind
from academicos.storage.db import connect_db, initialize_db


def test_candidate_inbox_orders_by_confidence_and_exposes_course_context() -> None:
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES ('c1', 'CEG2136', 'Architecture', '2026F', 'A00')"
    )
    conn.commit()

    persist_candidate_event(
        conn,
        CandidateEvent(
            id="low",
            kind=EventKind.NEW_MATERIAL,
            course_id="c1",
            confidence=0.7,
            effective_at=datetime(2026, 9, 25, tzinfo=UTC),
        ),
    )
    persist_candidate_event(
        conn,
        CandidateEvent(
            id="high",
            kind=EventKind.QUIZ_ANNOUNCED,
            course_id="c1",
            confidence=0.95,
            effective_at=datetime(2026, 9, 26, tzinfo=UTC),
            payload={"date": "2026-09-26"},
        ),
    )

    items = list_candidate_inbox(conn)

    assert [item.id for item in items] == ["high", "low"]
    assert items[0].course_code == "CEG2136"
    assert items[0].course_section == "A00"
    assert items[0].payload == {"date": "2026-09-26"}


def test_candidate_inbox_can_filter_non_pending_status() -> None:
    conn = connect_db(":memory:")
    initialize_db(conn)
    persist_candidate_event(
        conn,
        CandidateEvent(
            id="rejected",
            kind=EventKind.NEW_MATERIAL,
            confidence=0.8,
            status=CandidateStatus.REJECTED,
        ),
    )

    assert list_candidate_inbox(conn) == []
    rows = list_candidate_inbox(conn, status=CandidateStatus.REJECTED)
    assert [item.id for item in rows] == ["rejected"]
