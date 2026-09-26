from __future__ import annotations

import pytest

from academicos.calendar.events import (
    CandidateTransitionError,
    accept_candidate_event,
    reject_candidate_event,
    rollback_candidate_event,
)
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


def _assignment(conn, due: str) -> str:
    persist_dataset(
        conn,
        dataset="assignments",
        payload=[{"Id": 42, "Name": "Assignment 2", "DueDate": due}],
        course_id="c1",
        org_unit_id="99",
    )
    reconcile_persisted_brightspace_tasks(conn)
    return conn.execute("SELECT id FROM tasks WHERE title='Assignment 2'").fetchone()["id"]


def _announcement(conn, *, news_id: int, due_text: str) -> str:
    ingest_announcements(
        conn,
        [
            {
                "Id": news_id,
                "Title": "Assignment 2 deadline extended",
                "Body": {"Text": f"The due date has been extended to {due_text}."},
                "StartDate": "2026-09-25T14:00:00Z",
            }
        ],
        course_id="c1",
        org_unit_id="99",
    )
    row = conn.execute(
        """
        SELECT ce.id
        FROM candidate_events AS ce
        JOIN candidate_evidence AS link ON link.candidate_event_id = ce.id
        JOIN evidence AS e ON e.id = link.evidence_id
        JOIN source_items AS si ON si.id = e.source_item_id
        WHERE ce.kind = 'deadline_changed'
          AND si.source_id = ?
        LIMIT 1
        """,
        (f"news:99:{news_id}",),
    ).fetchone()
    assert row is not None
    return row["id"]


def test_new_pending_deadline_supersedes_old_pending_and_reject_restores_it() -> None:
    conn = _db()
    _assignment(conn, "2026-10-01T23:59:00-04:00")

    first = _announcement(conn, news_id=501, due_text="October 5, 2026 at 11:59 PM")
    second = _announcement(conn, news_id=502, due_text="October 7, 2026 at 11:59 PM")

    first_row = conn.execute(
        "SELECT status, superseded_by_candidate_id FROM candidate_events WHERE id=?",
        (first,),
    ).fetchone()
    second_row = conn.execute(
        "SELECT status FROM candidate_events WHERE id=?",
        (second,),
    ).fetchone()
    assert first_row["status"] == "superseded"
    assert first_row["superseded_by_candidate_id"] == second
    assert second_row["status"] == "pending"

    reject_candidate_event(conn, second)
    restored = conn.execute(
        "SELECT status, superseded_by_candidate_id FROM candidate_events WHERE id=?",
        (first,),
    ).fetchone()
    assert restored["status"] == "pending"
    assert restored["superseded_by_candidate_id"] is None


def test_accepting_new_deadline_supersedes_applied_change_and_rollback_reactivates_parent() -> None:
    conn = _db()
    task_id = _assignment(conn, "2026-10-01T23:59:00-04:00")

    first = _announcement(conn, news_id=601, due_text="October 5, 2026 at 11:59 PM")
    accept_candidate_event(conn, first)
    second = _announcement(conn, news_id=602, due_text="October 7, 2026 at 11:59 PM")
    accept_candidate_event(conn, second)

    task = conn.execute("SELECT due_at FROM tasks WHERE id=?", (task_id,)).fetchone()
    assert task["due_at"] == "2026-10-07T23:59:00-04:00"

    first_candidate = conn.execute(
        "SELECT status, superseded_by_candidate_id FROM candidate_events WHERE id=?",
        (first,),
    ).fetchone()
    assert first_candidate["status"] == "superseded"
    assert first_candidate["superseded_by_candidate_id"] == second

    changes = conn.execute(
        """
        SELECT candidate_event_id, status, supersedes_change_id, id
        FROM task_deadline_changes
        WHERE task_id=?
        ORDER BY applied_at, id
        """,
        (task_id,),
    ).fetchall()
    by_candidate = {row["candidate_event_id"]: row for row in changes}
    assert by_candidate[first]["status"] == "superseded"
    assert by_candidate[second]["status"] == "applied"
    assert by_candidate[second]["supersedes_change_id"] == by_candidate[first]["id"]

    with pytest.raises(CandidateTransitionError):
        rollback_candidate_event(conn, first)

    result = rollback_candidate_event(conn, second)
    assert result.restored_due_at == "2026-10-05T23:59:00-04:00"
    assert result.reactivated_candidate_id == first

    task = conn.execute("SELECT due_at FROM tasks WHERE id=?", (task_id,)).fetchone()
    assert task["due_at"] == "2026-10-05T23:59:00-04:00"
    first_candidate = conn.execute(
        "SELECT status, superseded_by_candidate_id FROM candidate_events WHERE id=?",
        (first,),
    ).fetchone()
    second_candidate = conn.execute(
        "SELECT status, rolled_back_at FROM candidate_events WHERE id=?",
        (second,),
    ).fetchone()
    assert first_candidate["status"] == "accepted"
    assert first_candidate["superseded_by_candidate_id"] is None
    assert second_candidate["status"] == "rolled_back"
    assert second_candidate["rolled_back_at"] is not None


def test_authoritative_brightspace_due_date_supersedes_applied_announcement_change() -> None:
    conn = _db()
    task_id = _assignment(conn, "2026-10-01T23:59:00-04:00")
    candidate = _announcement(conn, news_id=701, due_text="October 5, 2026 at 11:59 PM")
    accept_candidate_event(conn, candidate)

    persist_dataset(
        conn,
        dataset="assignments",
        payload=[{"Id": 42, "Name": "Assignment 2", "DueDate": "2026-10-09T23:59:00-04:00"}],
        course_id="c1",
        org_unit_id="99",
    )
    reconcile_persisted_brightspace_tasks(conn)

    task = conn.execute("SELECT due_at FROM tasks WHERE id=?", (task_id,)).fetchone()
    candidate_row = conn.execute(
        "SELECT status, superseded_by_candidate_id FROM candidate_events WHERE id=?",
        (candidate,),
    ).fetchone()
    change = conn.execute(
        "SELECT status FROM task_deadline_changes WHERE candidate_event_id=?",
        (candidate,),
    ).fetchone()

    assert task["due_at"] == "2026-10-09T23:59:00-04:00"
    assert candidate_row["status"] == "superseded"
    assert candidate_row["superseded_by_candidate_id"] is None
    assert change["status"] == "superseded"

    with pytest.raises(CandidateTransitionError):
        rollback_candidate_event(conn, candidate)
