from datetime import date

import pytest

from academicos.calendar.events import (
    CandidateConflictError,
    CandidateTransitionError,
    accept_candidate_event,
    persist_candidate_event,
    reject_candidate_event,
)
from academicos.calendar.models import CandidateEvent, EventKind, OverrideKind
from academicos.calendar.timetable import TimetableDocument, import_timetable
from academicos.calendar.truth import effective_sessions_for_date, effective_sessions_for_range
from academicos.storage.db import connect_db, initialize_db


def _db():
    conn = connect_db(":memory:")
    initialize_db(conn)
    doc = TimetableDocument.model_validate(
        {
            "term": "2026F",
            "courses": [
                {
                    "code": "CEG2136",
                    "name": "Computer Architecture I",
                    "section": "A00",
                    "sessions": [
                        {
                            "session_type": "lecture",
                            "days": ["MO", "TH"],
                            "start_time": "14:30",
                            "end_time": "15:50",
                            "start_date": "2026-09-01",
                            "end_date": "2026-12-04",
                            "location": "SITE",
                            "group": "A00"
                        }
                    ]
                }
            ]
        }
    )
    import_timetable(conn, doc)
    return conn


def _monday_session_id(conn):
    return conn.execute(
        "SELECT id FROM course_sessions WHERE weekday = 0"
    ).fetchone()["id"]


def test_accept_cancellation_materializes_override() -> None:
    conn = _db()
    session_id = _monday_session_id(conn)
    event = CandidateEvent(
        id="cand-cancel",
        kind=EventKind.CLASS_CANCELLED,
        target_ref=session_id,
        effective_at="2026-09-28T14:30:00-04:00",
        confidence=0.99,
    )
    persist_candidate_event(conn, event)

    result = accept_candidate_event(conn, event.id, automatic=True)

    assert result.status.value == "auto_accepted"
    row = conn.execute(
        "SELECT * FROM event_overrides WHERE candidate_event_id = ?",
        (event.id,),
    ).fetchone()
    assert row["kind"] == OverrideKind.CANCELLED.value
    assert effective_sessions_for_date(conn, date(2026, 9, 28)) == []


def test_auto_accept_is_confidence_gated() -> None:
    conn = _db()
    event = CandidateEvent(
        id="cand-low",
        kind=EventKind.CLASS_CANCELLED,
        target_ref=_monday_session_id(conn),
        effective_at="2026-09-28T14:30:00-04:00",
        confidence=0.70,
    )
    persist_candidate_event(conn, event)

    with pytest.raises(CandidateTransitionError):
        accept_candidate_event(conn, event.id, automatic=True, auto_threshold=0.95)

    status = conn.execute(
        "SELECT status FROM candidate_events WHERE id = ?",
        (event.id,),
    ).fetchone()["status"]
    assert status == "pending"


def test_rejected_candidate_cannot_be_accepted() -> None:
    conn = _db()
    event = CandidateEvent(
        id="cand-reject",
        kind=EventKind.CLASS_CANCELLED,
        target_ref=_monday_session_id(conn),
        effective_at="2026-09-28T14:30:00-04:00",
        confidence=0.99,
    )
    persist_candidate_event(conn, event)
    reject_candidate_event(conn, event.id)

    with pytest.raises(CandidateTransitionError):
        accept_candidate_event(conn, event.id)


def test_same_kind_override_conflict_is_blocked() -> None:
    conn = _db()
    session_id = _monday_session_id(conn)

    for candidate_id, room in [("cand-room-a", "MRT 218"), ("cand-room-b", "SITE 5084")]:
        persist_candidate_event(
            conn,
            CandidateEvent(
                id=candidate_id,
                kind=EventKind.CLASS_LOCATION_CHANGED,
                target_ref=session_id,
                effective_at="2026-09-28T14:30:00-04:00",
                payload={"new_location": room},
                confidence=0.99,
            ),
        )

    accept_candidate_event(conn, "cand-room-a")

    with pytest.raises(CandidateConflictError):
        accept_candidate_event(conn, "cand-room-b")

    item = effective_sessions_for_date(conn, date(2026, 9, 28))[0]
    assert item.location == "MRT 218"


def test_week_range_returns_each_day() -> None:
    conn = _db()
    week = effective_sessions_for_range(
        conn,
        date(2026, 9, 28),
        date(2026, 10, 4),
    )

    assert len(week) == 7
    assert len(week[date(2026, 9, 28)]) == 1
    assert len(week[date(2026, 10, 1)]) == 1
