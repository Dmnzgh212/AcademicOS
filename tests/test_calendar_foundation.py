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

    assert schema_version(conn) == 7
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


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
        PlanBlock(id="b", task_id="t", start_at=when, end_at=when)


def test_v1_database_migrates_to_latest_schema() -> None:
    conn = connect_db(":memory:")
    conn.executescript(
        """
        CREATE TABLE schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO schema_meta(key, value) VALUES ('schema_version', '1');

        CREATE TABLE courses (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            term TEXT NOT NULL
        );
        """
    )

    initialize_db(conn)

    assert schema_version(conn) == 7
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(courses)").fetchall()
    }
    assert "section" in columns
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "sync_state" in tables
    assert "source_health" in tables
    assert "file_manifest" in tables
    assert "endpoint_capabilities" in tables
    assert "sync_runs" in tables
    assert "sync_run_sources" in tables
    assert "task_source_links" in tables
    assert "task_deadline_changes" in tables
