from __future__ import annotations

from datetime import date, datetime, UTC
from zoneinfo import ZoneInfo

import pytest

from academicos.planner.engine import chunk_minutes, plan_tasks
from academicos.planner.velocity import estimate_velocity
from academicos.storage.db import connect_db, initialize_db


def _db():
    conn = connect_db(":memory:")
    initialize_db(conn)
    conn.execute(
        "INSERT INTO courses(id, code, name, term, section) VALUES ('c1', 'CEG2136', 'Architecture', '2026F', 'A00')"
    )
    conn.commit()
    return conn


def test_velocity_uses_shrunken_personal_history() -> None:
    conn = _db()
    conn.executemany(
        """
        INSERT INTO tasks(
            id, course_id, title, task_type, initial_estimate_minutes,
            remaining_minutes, actual_spent_minutes, progress, status
        ) VALUES (?, 'c1', ?, 'lab', 60, 0, 120, 1.0, 'done')
        """,
        [("done-1", "Lab 1"), ("done-2", "Lab 2")],
    )
    conn.commit()

    estimate = estimate_velocity(conn, course_id="c1", task_type="lab")

    assert estimate.scope == "course_task_type"
    assert estimate.samples == 2
    assert estimate.multiplier == pytest.approx(1.4)


def test_chunking_balances_long_work_without_tiny_tail() -> None:
    chunks = chunk_minutes(250, preferred_minutes=90, min_minutes=30, max_minutes=120)
    assert sum(chunks) == 250
    assert max(chunks) <= 120
    assert min(chunks) >= 30


def test_planner_prioritizes_near_deadline_task() -> None:
    conn = _db()
    conn.executemany(
        """
        INSERT INTO tasks(
            id, course_id, title, task_type, due_at,
            initial_estimate_minutes, remaining_minutes, importance, status
        ) VALUES (?, 'c1', ?, 'assignment', ?, ?, ?, ?, 'pending')
        """,
        [
            ("urgent", "Due soon", "2026-09-28T10:00:00-04:00", 60, 60, 0.6),
            ("later", "Due later", "2026-10-05T23:59:00-04:00", 120, 120, 0.9),
        ],
    )
    conn.commit()

    result = plan_tasks(
        conn,
        start_date=date(2026, 9, 28),
        end_date=date(2026, 9, 28),
        now=datetime(2026, 9, 28, 8, 0, tzinfo=ZoneInfo("America/Toronto")),
        persist=False,
    )

    assert result.blocks
    assert result.blocks[0].task_id == "urgent"
    assert result.blocks[0].start_at.hour == 8


def test_planner_respects_truth_calendar_and_pinned_blocks() -> None:
    conn = _db()
    conn.execute(
        """
        INSERT INTO course_sessions(
            id, course_id, session_type, weekday, start_time, end_time,
            start_date, end_date, location, delivery_mode
        ) VALUES ('lecture', 'c1', 'lecture', 0, '09:00', '10:00',
                  '2026-09-01', '2026-12-04', 'SITE', 'in_person')
        """
    )
    conn.execute(
        """
        INSERT INTO tasks(
            id, course_id, title, task_type, due_at,
            initial_estimate_minutes, remaining_minutes, importance, status
        ) VALUES ('task', 'c1', 'Work', 'assignment', '2026-09-28T18:00:00-04:00',
                  60, 60, 0.8, 'pending')
        """
    )
    conn.execute(
        """
        INSERT INTO plan_blocks(id, task_id, start_at, end_at, state, pinned)
        VALUES ('pin', 'task', '2026-09-28T10:10:00-04:00', '2026-09-28T11:10:00-04:00', 'planned', 1)
        """
    )
    conn.commit()

    result = plan_tasks(
        conn,
        start_date=date(2026, 9, 28),
        end_date=date(2026, 9, 28),
        now=datetime(2026, 9, 28, 8, 30, tzinfo=ZoneInfo("America/Toronto")),
        persist=False,
    )

    assert len(result.blocks) == 1
    block = result.blocks[0]
    assert block.start_at >= datetime(2026, 9, 28, 11, 10, tzinfo=ZoneInfo("America/Toronto"))


def test_planner_persists_new_run_and_replaces_only_movable_plans() -> None:
    conn = _db()
    conn.execute(
        """
        INSERT INTO tasks(
            id, course_id, title, task_type, due_at,
            initial_estimate_minutes, remaining_minutes, importance, status
        ) VALUES ('task', 'c1', 'Work', 'assignment', '2026-09-29T23:59:00-04:00',
                  60, 60, 0.8, 'pending')
        """
    )
    conn.execute(
        """
        INSERT INTO plan_blocks(id, task_id, start_at, end_at, state, pinned, planner_run_id)
        VALUES ('old', 'task', '2026-09-28T15:00:00-04:00', '2026-09-28T16:00:00-04:00', 'planned', 0, 'old-run')
        """
    )
    conn.commit()

    result = plan_tasks(
        conn,
        start_date=date(2026, 9, 28),
        end_date=date(2026, 9, 29),
        now=datetime(2026, 9, 28, 8, 0, tzinfo=UTC),
        persist=True,
    )

    assert result.blocks
    assert conn.execute("SELECT COUNT(*) FROM plan_blocks WHERE id = 'old'").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM plan_blocks WHERE planner_run_id = ?",
        (result.planner_run_id,),
    ).fetchone()[0] == len(result.blocks)
