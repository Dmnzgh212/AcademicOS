from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from academicos.sources.run_ledger import record_sync_run
from academicos.sources.sync import SyncReport


def _iso_local(day, hh: int, mm: int, tz: ZoneInfo) -> str:  # noqa: ANN001
    return datetime.combine(day, time(hh, mm), tzinfo=tz).isoformat()


def _clear_demo(conn: sqlite3.Connection) -> None:
    tables = (
        "task_deadline_changes",
        "task_source_links",
        "plan_blocks",
        "tasks",
        "event_overrides",
        "candidate_evidence",
        "candidate_events",
        "evidence",
        "activity_feed",
        "source_items",
        "sync_run_sources",
        "sync_runs",
        "course_sessions",
        "courses",
    )
    with conn:
        for table in tables:
            conn.execute(f"DELETE FROM {table}")


def seed_demo(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    timezone_name: str = "America/Toronto",
    reset: bool = False,
) -> dict[str, int]:
    """Seed a privacy-safe synthetic semester for UI/product evaluation."""
    tz = ZoneInfo(timezone_name)
    local_now = now or datetime.now(tz)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=tz)
    else:
        local_now = local_now.astimezone(tz)

    existing = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    if existing and not reset:
        raise ValueError("demo seeding requires an empty database; pass reset=True for a demo DB")
    if reset:
        _clear_demo(conn)

    monday = local_now.date() - timedelta(days=local_now.weekday())
    semester_start = monday - timedelta(weeks=3)
    semester_end = monday + timedelta(weeks=10)

    courses = [
        ("demo-sys", "SYS2101", "Systems and Architecture", "DEMO", "A00"),
        ("demo-dsa", "CSC2200", "Data Structures", "DEMO", "A00"),
        ("demo-mat", "MAT2300", "Multivariable Calculus", "DEMO", "A00"),
        ("demo-cir", "ECE2100", "Circuit Analysis", "DEMO", "B00"),
        ("demo-se", "SEG2100", "Software Design", "DEMO", "B00"),
        ("demo-phy", "PHY2200", "Waves and Fields", "DEMO", "A00"),
    ]

    sessions = [
        ("sys-mo", "demo-sys", "lecture", 0, "10:00", "11:20", "ENG 201", "in_person"),
        ("sys-we", "demo-sys", "lecture", 2, "10:00", "11:20", "ENG 201", "in_person"),
        ("dsa-tu", "demo-dsa", "lecture", 1, "13:00", "14:20", "LAB 120", "in_person"),
        ("dsa-th", "demo-dsa", "lecture", 3, "13:00", "14:20", "LAB 120", "in_person"),
        ("mat-mo", "demo-mat", "lecture", 0, "08:30", "09:50", "SCI 101", "in_person"),
        ("mat-th", "demo-mat", "lecture", 3, "08:30", "09:50", "SCI 101", "in_person"),
        ("cir-tu", "demo-cir", "lecture", 1, "10:00", "11:20", "ENG 105", "in_person"),
        ("cir-fr", "demo-cir", "lab", 4, "13:00", "15:50", "LAB 302", "in_person"),
        ("se-we", "demo-se", "lecture", 2, "14:30", "15:50", "SITE 200", "in_person"),
        ("se-fr", "demo-se", "tutorial", 4, "10:00", "11:20", "SITE 200", "in_person"),
        ("phy-tu", "demo-phy", "lecture", 1, "16:00", "17:20", "SCI 240", "in_person"),
        ("phy-th", "demo-phy", "lecture", 3, "16:00", "17:20", "SCI 240", "in_person"),
    ]

    with conn:
        conn.executemany(
            "INSERT INTO courses(id, code, name, term, section) VALUES (?, ?, ?, ?, ?)",
            courses,
        )
        conn.executemany(
            """
            INSERT INTO course_sessions(
                id, course_id, session_type, weekday, start_time, end_time,
                start_date, end_date, location, delivery_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (*row[:6], semester_start.isoformat(), semester_end.isoformat(), *row[6:])
                for row in sessions
            ],
        )

    task_specs = [
        ("task-circuit", "demo-cir", "Circuit lab report", "lab", 0, 23, 59, 120, 90, 0.92, 0.25, "in_progress"),
        ("task-sys", "demo-sys", "Quiz 2 review", "quiz", 1, 18, 0, 75, 60, 0.82, 0.10, "pending"),
        ("task-dsa", "demo-dsa", "Assignment 2", "assignment", 2, 23, 59, 240, 150, 0.95, 0.38, "in_progress"),
        ("task-mat", "demo-mat", "Problem set 4", "problem_set", 3, 20, 0, 120, 70, 0.74, 0.42, "in_progress"),
        ("task-phy", "demo-phy", "Tutorial preparation", "tutorial", 4, 16, 0, 60, 45, 0.58, 0.20, "pending"),
        ("task-se", "demo-se", "Sprint milestone", "project", 5, 21, 0, 360, 240, 0.88, 0.30, "in_progress"),
    ]
    with conn:
        for task in task_specs:
            task_id, course_id, title, task_type, offset, hh, mm, initial, remaining, importance, progress, status = task
            due_day = local_now.date() + timedelta(days=offset)
            conn.execute(
                """
                INSERT INTO tasks(
                    id, course_id, title, task_type, due_at,
                    initial_estimate_minutes, remaining_minutes, actual_spent_minutes,
                    progress, importance, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    course_id,
                    title,
                    task_type,
                    _iso_local(due_day, hh, mm, tz),
                    initial,
                    remaining,
                    max(0, initial - remaining),
                    progress,
                    importance,
                    status,
                ),
            )

    plan_specs = [
        ("plan-circuit", "task-circuit", 18, 0, 19, 30, 1),
        ("plan-sys", "task-sys", 20, 0, 21, 0, 0),
        ("plan-dsa", "task-dsa", 21, 15, 22, 15, 0),
    ]
    with conn:
        for block_id, task_id, sh, sm, eh, em, pinned in plan_specs:
            conn.execute(
                """
                INSERT INTO plan_blocks(id, task_id, start_at, end_at, state, pinned, planner_run_id)
                VALUES (?, ?, ?, ?, 'planned', ?, 'demo-planner')
                """,
                (
                    block_id,
                    task_id,
                    _iso_local(local_now.date(), sh, sm, tz),
                    _iso_local(local_now.date(), eh, em, tz),
                    pinned,
                ),
            )

    source_rows = [
        (
            "demo-source-move",
            "brightspace",
            "demo:announcement:move",
            "demo-dsa",
            local_now.isoformat(),
            local_now.isoformat(),
            "demo-move",
            "Tuesday lecture moved to 14:30 in LAB 220.",
            json.dumps({"Title": "Lecture room update"}),
        ),
        (
            "demo-source-deadline",
            "email",
            "demo:mail:deadline",
            "demo-se",
            local_now.isoformat(),
            local_now.isoformat(),
            "demo-deadline",
            "Sprint milestone deadline extended to Friday at 21:00.",
            json.dumps({"Subject": "Sprint milestone deadline"}),
        ),
    ]
    with conn:
        conn.executemany(
            """
            INSERT INTO source_items(
                id, source_type, source_id, course_id, source_timestamp,
                fetched_at, content_hash, raw_text, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            source_rows,
        )
        conn.executemany(
            "INSERT INTO evidence(id, source_item_id, excerpt) VALUES (?, ?, ?)",
            [
                ("ev-move", "demo-source-move", "Tuesday lecture moved to 14:30 in LAB 220."),
                ("ev-deadline", "demo-source-deadline", "deadline extended to Friday at 21:00"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO candidate_events(
                id, kind, course_id, target_ref, effective_at, payload_json, confidence, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            [
                (
                    "candidate-move",
                    "class_moved",
                    "demo-dsa",
                    None,
                    _iso_local(local_now.date() + timedelta(days=1), 14, 30, tz),
                    json.dumps({"new_start_time": "14:30", "location": "LAB 220"}),
                    0.94,
                ),
                (
                    "candidate-deadline",
                    "deadline_changed",
                    "demo-se",
                    "task-se",
                    _iso_local(local_now.date() + timedelta(days=5), 21, 0, tz),
                    json.dumps({"new_due_at": _iso_local(local_now.date() + timedelta(days=5), 21, 0, tz)}),
                    0.91,
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO candidate_evidence(candidate_event_id, evidence_id) VALUES (?, ?)",
            [("candidate-move", "ev-move"), ("candidate-deadline", "ev-deadline")],
        )

        activity_specs = [
            ("act-1", "demo-mat", "material", "Week 4 worked examples uploaded", -1, 19, 40),
            ("act-2", "demo-cir", "announcement", "Lab instructions updated", 0, 8, 25),
            ("act-3", "demo-dsa", "assignment", "Assignment 2 rubric changed", 0, 9, 10),
            ("act-4", "demo-se", "announcement", "Sprint checkpoint posted", 0, 10, 5),
        ]
        for activity_id, course_id, kind, title, day_offset, hh, mm in activity_specs:
            occurred_day = local_now.date() + timedelta(days=day_offset)
            conn.execute(
                """
                INSERT INTO activity_feed(id, course_id, kind, title, occurred_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (activity_id, course_id, kind, title, _iso_local(occurred_day, hh, mm, tz)),
            )

    report = SyncReport(
        changed=34,
        unchanged=87,
        sources_ok=[
            "brightspace:demo-sys",
            "brightspace:demo-dsa",
            "brightspace:demo-mat",
            "brightspace:demo-cir",
            "brightspace:demo-se",
            "brightspace:demo-phy",
        ],
    )
    record_sync_run(
        conn,
        report,
        started_at=(local_now - timedelta(minutes=4)).astimezone(UTC),
        finished_at=(local_now - timedelta(minutes=2)).astimezone(UTC),
        mode="demo",
    )

    conn.commit()
    return {
        "courses": len(courses),
        "sessions": len(sessions),
        "tasks": len(task_specs),
        "plan_blocks": len(plan_specs),
        "changes": 2,
        "activities": 4,
    }
