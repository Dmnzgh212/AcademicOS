from __future__ import annotations

from datetime import datetime, timezone

from academicos.calendar.truth import effective_sessions_for_date
from academicos.sources.brightspace.announcements import (
    ingest_announcements,
    normalize_announcement,
)
from academicos.storage.db import connect_db, initialize_db


def _calendar_db():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES ('c1', 'CEG2136', 'Architecture', '2026F', 'A00')"
    )
    conn.execute(
        """
        INSERT INTO course_sessions(
            id, course_id, session_type, weekday,
            start_time, end_time, start_date, end_date, location, delivery_mode
        ) VALUES ('s1', 'c1', 'lecture', 4, '10:00', '11:20', '2026-09-01', '2026-12-04', 'SITE 1000', 'in_person')
        """
    )
    conn.commit()
    return conn


def _announcement(body: str, *, identifier: int = 10) -> dict:
    return {
        "Id": identifier,
        "Title": "Friday lecture update",
        "Body": {"Text": body, "Html": f"<p>{body}</p>"},
        "StartDate": "2026-09-24T14:00:00Z",
    }


def test_normalize_announcement_uses_html_when_plain_text_missing() -> None:
    item = normalize_announcement(
        {
            "Id": 2,
            "Title": "Update",
            "Body": {"Html": "<p>Hello <strong>class</strong>.</p><p>See you Friday.</p>"},
            "CreatedDate": "2026-09-24T12:00:00Z",
        }
    )
    assert item.body == "Hello class. See you Friday."


def test_cancellation_becomes_evidence_backed_candidate_and_is_idempotent() -> None:
    conn = _calendar_db()
    raw = [_announcement("There will be no lecture tomorrow.")]

    first = ingest_announcements(conn, raw, course_id="c1", org_unit_id="123")
    assert first == {
        "fetched": 1,
        "changed": 1,
        "unchanged": 0,
        "candidates": 1,
        "auto_accepted": 0,
        "auto_skipped": 0,
    }

    source = conn.execute("SELECT * FROM source_items").fetchone()
    candidate = conn.execute("SELECT * FROM candidate_events").fetchone()
    link = conn.execute("SELECT * FROM candidate_evidence").fetchone()

    assert source["source_id"] == "news:123:10"
    assert candidate["kind"] == "class_cancelled"
    assert candidate["target_ref"] == "s1"
    assert '"occurrence_date": "2026-09-25"' in candidate["payload_json"]
    assert link["candidate_event_id"] == candidate["id"]

    second = ingest_announcements(conn, raw, course_id="c1", org_unit_id="123")
    assert second["changed"] == 0
    assert second["unchanged"] == 1
    assert second["candidates"] == 0


def test_edited_announcement_replaces_only_pending_candidates() -> None:
    conn = _calendar_db()
    ingest_announcements(
        conn,
        [_announcement("There will be no lecture tomorrow.")],
        course_id="c1",
        org_unit_id="123",
    )

    result = ingest_announcements(
        conn,
        [_announcement("Tomorrow's lecture will be held online on Zoom.")],
        course_id="c1",
        org_unit_id="123",
    )

    assert result["changed"] == 1
    rows = conn.execute("SELECT kind, status FROM candidate_events").fetchall()
    assert [(row["kind"], row["status"]) for row in rows] == [
        ("class_mode_changed", "pending")
    ]


def test_explicit_cancellation_can_auto_accept_into_truth_calendar() -> None:
    conn = _calendar_db()
    result = ingest_announcements(
        conn,
        [_announcement("There will be no lecture tomorrow.")],
        course_id="c1",
        org_unit_id="123",
        auto_accept=True,
        auto_threshold=0.98,
    )

    assert result["auto_accepted"] == 1
    assert conn.execute("SELECT COUNT(*) FROM event_overrides").fetchone()[0] == 1

    sessions = effective_sessions_for_date(
        conn,
        datetime(2026, 9, 25, tzinfo=timezone.utc).date(),
    )
    assert sessions == []


def test_deadline_extension_is_candidate_but_not_auto_materialized() -> None:
    conn = _calendar_db()
    result = ingest_announcements(
        conn,
        [
            {
                "Id": 44,
                "Title": "Assignment deadline extension",
                "Body": {"Text": "The assignment due date has been extended until Friday at 11:59 PM."},
                "StartDate": "2026-09-23T13:00:00Z",
            }
        ],
        course_id="c1",
        org_unit_id="123",
        auto_accept=True,
    )

    row = conn.execute("SELECT kind, payload_json, status FROM candidate_events").fetchone()
    assert row["kind"] == "deadline_changed"
    assert "2026-09-25T23:59:00" in row["payload_json"]
    assert row["status"] == "pending"
    assert result["auto_skipped"] == 0
