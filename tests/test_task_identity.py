from __future__ import annotations

from academicos.calendar.events import accept_candidate_event
from academicos.sources.brightspace.announcements import ingest_announcements
from academicos.sources.brightspace.collector import persist_dataset
from academicos.sources.brightspace.task_sync import reconcile_persisted_brightspace_tasks
from academicos.storage.db import connect_db, initialize_db


def _db():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
        ("c1", "CEG2136", "Computer Architecture I", "20269", "A00"),
    )
    conn.commit()
    return conn


def _persist_assignment(conn, *, due: str) -> None:
    persist_dataset(
        conn,
        dataset="assignments",
        payload=[{"Id": 42, "Name": "Assignment 2", "DueDate": due}],
        course_id="c1",
        org_unit_id="99",
    )


def test_structured_brightspace_objects_create_stable_tasks() -> None:
    conn = _db()
    _persist_assignment(conn, due="2026-10-01T23:59:00-04:00")
    persist_dataset(
        conn,
        dataset="quizzes",
        payload=[{"Id": 7, "Name": "Quiz 1", "DueDate": "2026-10-03T18:00:00-04:00"}],
        course_id="c1",
        org_unit_id="99",
    )

    report = reconcile_persisted_brightspace_tasks(conn)

    assert report.created == 2
    tasks = conn.execute(
        "SELECT id, title, task_type, due_at, remaining_minutes FROM tasks ORDER BY title"
    ).fetchall()
    assert [(row["title"], row["task_type"]) for row in tasks] == [
        ("Assignment 2", "assignment"),
        ("Quiz 1", "quiz"),
    ]
    assert tasks[0]["remaining_minutes"] == 90
    assert tasks[1]["remaining_minutes"] == 45
    assert conn.execute("SELECT COUNT(*) AS n FROM task_source_links").fetchone()["n"] == 2


def test_structured_due_date_update_preserves_task_identity_and_progress() -> None:
    conn = _db()
    _persist_assignment(conn, due="2026-10-01T23:59:00-04:00")
    reconcile_persisted_brightspace_tasks(conn)
    first = conn.execute("SELECT id FROM tasks WHERE title='Assignment 2'").fetchone()["id"]
    conn.execute(
        "UPDATE tasks SET progress=0.4, actual_spent_minutes=55, remaining_minutes=70 WHERE id=?",
        (first,),
    )
    conn.commit()

    _persist_assignment(conn, due="2026-10-05T23:59:00-04:00")
    report = reconcile_persisted_brightspace_tasks(conn)
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (first,)).fetchone()

    assert report.updated == 1
    assert task["id"] == first
    assert task["due_at"] == "2026-10-05T23:59:00-04:00"
    assert task["progress"] == 0.4
    assert task["actual_spent_minutes"] == 55
    assert task["remaining_minutes"] == 70


def test_deadline_announcement_uniquely_targets_task_and_acceptance_updates_due_date() -> None:
    conn = _db()
    _persist_assignment(conn, due="2026-10-01T23:59:00-04:00")
    reconcile_persisted_brightspace_tasks(conn)
    task_before = conn.execute("SELECT id, due_at FROM tasks WHERE title='Assignment 2'").fetchone()

    summary = ingest_announcements(
        conn,
        [
            {
                "Id": 501,
                "Title": "Assignment 2 deadline extended",
                "Body": {"Text": "The due date has been extended to October 5, 2026 at 11:59 PM."},
                "StartDate": "2026-09-25T14:00:00Z",
            }
        ],
        course_id="c1",
        org_unit_id="99",
    )

    assert summary["candidates"] == 1
    candidate = conn.execute(
        "SELECT id, kind, target_ref, confidence, payload_json FROM candidate_events"
    ).fetchone()
    assert candidate["kind"] == "deadline_changed"
    assert candidate["target_ref"] == task_before["id"]
    assert candidate["confidence"] == 0.94

    result = accept_candidate_event(conn, candidate["id"])
    task_after = conn.execute("SELECT due_at FROM tasks WHERE id=?", (task_before["id"],)).fetchone()
    audit = conn.execute(
        "SELECT old_due_at, new_due_at FROM task_deadline_changes WHERE task_id=?",
        (task_before["id"],),
    ).fetchone()

    assert result.action_type == "task_deadline_update"
    assert task_after["due_at"] == "2026-10-05T23:59:00-04:00"
    assert audit["old_due_at"] == "2026-10-01T23:59:00-04:00"
    assert audit["new_due_at"] == "2026-10-05T23:59:00-04:00"


def test_ambiguous_deadline_announcement_does_not_guess_target() -> None:
    conn = _db()
    for task_id in ("manual-a", "manual-b"):
        conn.execute(
            """
            INSERT INTO tasks(
                id, course_id, title, task_type, due_at,
                initial_estimate_minutes, remaining_minutes
            ) VALUES (?, 'c1', 'Assignment 2', 'assignment', ?, 60, 60)
            """,
            (task_id, "2026-10-01T23:59:00-04:00"),
        )
    conn.commit()

    ingest_announcements(
        conn,
        [
            {
                "Id": 502,
                "Title": "Assignment 2 deadline extended",
                "Body": {"Text": "The deadline has been extended to October 6, 2026."},
                "StartDate": "2026-09-25T14:00:00Z",
            }
        ],
        course_id="c1",
        org_unit_id="99",
    )
    candidate = conn.execute(
        "SELECT target_ref, confidence FROM candidate_events WHERE kind='deadline_changed'"
    ).fetchone()

    assert candidate["target_ref"] is None
    assert candidate["confidence"] == 0.82
