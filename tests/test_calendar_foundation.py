from datetime import date, datetime, time, timezone

import pytest
from pydantic import ValidationError

from academicos.calendar.models import (
    CandidateEvent,
    EventKind,
    PlanBlock,
    RecurringSession,
    SessionType,
)
from academicos.storage.db import connect_db, initialize_db, schema_version


def test_schema_initializes_with_foreign_keys() -> None:
    conn = connect_db(":memory:")
    initialize_db(conn)

    assert schema_version(conn) == 1
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    assert {
        "courses",
        "source_items",
        "evidence",
        "course_sessions",
        "candidate_events",
        "candidate_evidence",
        "event_overrides",
        "tasks",
        "plan_blocks",
        "activity_feed",
    } <= tables


def test_recurring_session_rejects_invalid_time_range() -> None:
    with pytest.raises(ValidationError):
        RecurringSession(
            id="s1",
            course_id="c1",
            session_type=SessionType.LECTURE,
            weekday=1,
            start_time=time(12, 0),
            end_time=time(11, 0),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 4),
        )


def test_candidate_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        CandidateEvent(
            id="candidate-1",
            kind=EventKind.CLASS_CANCELLED,
            confidence=1.2,
        )


def test_plan_block_requires_positive_duration() -> None:
    when = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)

    with pytest.raises(ValidationError):
        PlanBlock(
            id="block-1",
            task_id="task-1",
            start_at=when,
            end_at=when,
        )
