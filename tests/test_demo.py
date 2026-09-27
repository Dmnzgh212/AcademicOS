from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from academicos.demo import seed_demo
from academicos.storage.db import connect_db, initialize_db
from academicos.web.app import render_dashboard


def _conn():  # noqa: ANN202
    conn = connect_db(":memory:")
    initialize_db(conn)
    return conn


def test_demo_seeds_rich_privacy_safe_state_and_renders_command_center() -> None:
    conn = _conn()
    now = datetime(2026, 9, 27, 9, 0, tzinfo=ZoneInfo("America/Toronto"))

    counts = seed_demo(conn, now=now)
    page = render_dashboard(conn, now.date(), now=now)

    assert counts == {
        "courses": 6,
        "sessions": 12,
        "tasks": 6,
        "plan_blocks": 3,
        "changes": 2,
        "activities": 4,
    }
    assert "Week calendar" in page
    assert "Today execution" in page
    assert "Work queue" in page
    assert "Changes inbox" in page
    assert "Source pulse" in page
    assert "Circuit lab report" in page
    assert "Data fresh" in page
    assert "movable" in page


def test_demo_refuses_to_seed_nonempty_database_without_reset() -> None:
    conn = _conn()
    now = datetime(2026, 9, 27, 9, 0, tzinfo=ZoneInfo("America/Toronto"))
    seed_demo(conn, now=now)

    with pytest.raises(ValueError, match="empty database"):
        seed_demo(conn, now=now)

    counts = seed_demo(conn, now=now, reset=True)
    assert counts["courses"] == 6
    assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 6
