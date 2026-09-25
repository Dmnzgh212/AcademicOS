from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from academicos.briefing import build_morning_brief
from academicos.storage.db import connect_db, initialize_db
from academicos.web.app import render_dashboard, serve_dashboard


def _db():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES ('c1', 'CEG2136', 'Architecture', '2026F', 'A00')"
    )
    conn.execute(
        """
        INSERT INTO course_sessions(
            id, course_id, session_type, weekday, start_time, end_time,
            start_date, end_date, location, delivery_mode
        ) VALUES ('s1', 'c1', 'lecture', 4, '10:00', '11:20',
                  '2026-09-01', '2026-12-04', 'SITE 1000', 'in_person')
        """
    )
    conn.execute(
        """
        INSERT INTO tasks(
            id, course_id, title, task_type, due_at,
            initial_estimate_minutes, remaining_minutes, importance, status
        ) VALUES ('t1', 'c1', 'Lab 2', 'lab', '2026-09-26T23:59:00-04:00',
                  120, 90, 0.8, 'pending')
        """
    )
    conn.execute(
        """
        INSERT INTO plan_blocks(
            id, task_id, start_at, end_at, state, pinned, planner_run_id
        ) VALUES ('p1', 't1', '2026-09-25T18:00:00-04:00',
                  '2026-09-25T19:00:00-04:00', 'planned', 0, 'run')
        """
    )
    conn.execute(
        """
        INSERT INTO candidate_events(
            id, kind, course_id, effective_at, payload_json, confidence, status
        ) VALUES ('candidate', 'quiz_announced', 'c1', '2026-09-28T00:00:00-04:00',
                  '{"date":"2026-09-28"}', 0.91, 'pending')
        """
    )
    conn.execute(
        """
        INSERT INTO activity_feed(
            id, course_id, kind, title, occurred_at
        ) VALUES ('activity', 'c1', 'announcement', 'New slides uploaded',
                  '2026-09-25T08:30:00-04:00')
        """
    )
    conn.commit()
    return conn


def test_morning_brief_combines_truth_changes_tasks_and_plan() -> None:
    conn = _db()
    now = datetime(2026, 9, 25, 9, 0, tzinfo=ZoneInfo("America/Toronto"))

    brief = build_morning_brief(conn, date(2026, 9, 25), now=now)

    assert [item.course_code for item in brief.sessions] == ["CEG2136"]
    assert [item.title for item in brief.activities] == ["New slides uploaded"]
    assert [item.id for item in brief.pending_changes] == ["candidate"]
    assert [item.id for item in brief.upcoming_tasks] == ["t1"]
    assert [item.id for item in brief.plan_blocks] == ["p1"]
    assert any("waiting for review" in alert for alert in brief.alerts)
    assert any("due within 48h" in alert for alert in brief.alerts)


def test_dashboard_is_local_self_contained_and_escapes_data() -> None:
    conn = _db()
    conn.execute(
        "UPDATE tasks SET title = '<script>alert(1)</script>' WHERE id = 't1'"
    )
    conn.commit()

    page = render_dashboard(
        conn,
        date(2026, 9, 25),
        now=datetime(2026, 9, 25, 9, 0, tzinfo=ZoneInfo("America/Toronto")),
    )

    assert "AcademicOS" in page
    assert "Today timeline" in page
    assert "Changes inbox" in page
    assert "Confirmed" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)</script>" not in page
    assert "fonts.googleapis.com" not in page
    assert "https://cdn" not in page


def test_dashboard_refuses_non_loopback_binding_by_default(tmp_path) -> None:  # noqa: ANN001
    try:
        serve_dashboard(tmp_path / "db.sqlite", host="0.0.0.0", port=0)
    except ValueError as exc:
        assert "non-loopback" in str(exc)
    else:
        raise AssertionError("dashboard unexpectedly allowed public bind")
