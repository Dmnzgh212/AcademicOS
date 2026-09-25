from datetime import date

from academicos.calendar.models import OverrideKind
from academicos.calendar.timetable import TimetableDocument, import_timetable
from academicos.calendar.truth import EffectiveSessionStatus, effective_sessions_for_date
from academicos.storage.db import connect_db, initialize_db


def _doc() -> TimetableDocument:
    return TimetableDocument.model_validate(
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
                            "start_date": "2026-09-09",
                            "end_date": "2026-12-04",
                            "location": "SITE",
                            "delivery_mode": "in_person",
                            "group": "A00",
                        }
                    ],
                }
            ],
        }
    )


def _db():
    conn = connect_db(":memory:")
    initialize_db(conn)
    import_timetable(conn, _doc())
    return conn


def test_timetable_import_is_idempotent() -> None:
    conn = connect_db(":memory:")
    initialize_db(conn)

    first = import_timetable(conn, _doc())
    second = import_timetable(conn, _doc())

    assert first == {"courses": 1, "sessions": 2}
    assert second == {"courses": 1, "sessions": 2}
    assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM course_sessions").fetchone()[0] == 2


def test_truth_calendar_materializes_base_session() -> None:
    conn = _db()
    sessions = effective_sessions_for_date(conn, date(2026, 9, 28))

    assert len(sessions) == 1
    item = sessions[0]
    assert item.course_code == "CEG2136"
    assert item.course_section == "A00"
    assert item.start_at.hour == 14
    assert item.start_at.minute == 30
    assert item.location == "SITE"
    assert item.status == EffectiveSessionStatus.SCHEDULED


def test_cancellation_is_hidden_by_default_and_auditable() -> None:
    conn = _db()
    session_id = conn.execute(
        "SELECT id FROM course_sessions WHERE weekday = 0"
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO event_overrides(id, session_id, effective_date, kind) VALUES (?, ?, ?, ?)",
        ("ov-cancel", session_id, "2026-09-28", OverrideKind.CANCELLED.value),
    )
    conn.commit()

    assert effective_sessions_for_date(conn, date(2026, 9, 28)) == []
    visible = effective_sessions_for_date(
        conn, date(2026, 9, 28), include_cancelled=True
    )
    assert len(visible) == 1
    assert visible[0].status == EffectiveSessionStatus.CANCELLED
    assert visible[0].applied_override_ids == ("ov-cancel",)


def test_location_override_updates_effective_session() -> None:
    conn = _db()
    session_id = conn.execute(
        "SELECT id FROM course_sessions WHERE weekday = 0"
    ).fetchone()["id"]
    conn.execute(
        """
        INSERT INTO event_overrides(
            id, session_id, effective_date, kind, new_location
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            "ov-room",
            session_id,
            "2026-09-28",
            OverrideKind.LOCATION_CHANGED.value,
            "MRT 218",
        ),
    )
    conn.commit()

    item = effective_sessions_for_date(conn, date(2026, 9, 28))[0]
    assert item.location == "MRT 218"
    assert item.applied_override_ids == ("ov-room",)


def test_moved_session_disappears_from_old_day_and_appears_on_new_day() -> None:
    conn = _db()
    session_id = conn.execute(
        "SELECT id FROM course_sessions WHERE weekday = 0"
    ).fetchone()["id"]
    conn.execute(
        """
        INSERT INTO event_overrides(
            id, session_id, effective_date, kind, new_start_at, new_end_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "ov-move",
            session_id,
            "2026-09-28",
            OverrideKind.MOVED.value,
            "2026-09-29T18:00:00-04:00",
            "2026-09-29T19:20:00-04:00",
        ),
    )
    conn.commit()

    assert effective_sessions_for_date(conn, date(2026, 9, 28)) == []
    moved = effective_sessions_for_date(conn, date(2026, 9, 29))
    assert len(moved) == 1
    assert moved[0].status == EffectiveSessionStatus.MOVED
    assert moved[0].occurrence_date == date(2026, 9, 28)
    assert moved[0].start_at.hour == 18


def test_reimport_reconciles_removed_sessions() -> None:
    conn = connect_db(":memory:")
    initialize_db(conn)
    import_timetable(conn, _doc())

    changed = TimetableDocument.model_validate(
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
                            "days": ["MO"],
                            "start_time": "14:30",
                            "end_time": "15:50",
                            "start_date": "2026-09-09",
                            "end_date": "2026-12-04",
                            "group": "A00",
                        }
                    ],
                }
            ],
        }
    )

    import_timetable(conn, changed)
    assert conn.execute("SELECT COUNT(*) FROM course_sessions").fetchone()[0] == 1
