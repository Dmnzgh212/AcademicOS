from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta


def course_calendar_window(
    conn: sqlite3.Connection,
    course_id: str,
    *,
    padding_days: int = 14,
) -> tuple[str, str]:
    """Return a bounded UTC window suitable for Brightspace calendar queries.

    Brightspace's ``calendar/events/myEvents`` route requires both startDateTime
    and endDateTime. Prefer the user-authoritative local timetable so calendar
    collection follows the actual semester. A broad rolling fallback keeps live
    diagnostics usable before a timetable has been imported.

    The timetable stores local calendar dates rather than instants. Padding the
    UTC date boundaries avoids losing events around timezone offsets, orientation
    week, make-up days, or exam-period edges without requiring course timezone
    conversion here.
    """
    row = conn.execute(
        """
        SELECT MIN(start_date) AS start_date, MAX(end_date) AS end_date
        FROM course_sessions
        WHERE course_id = ?
        """,
        (course_id,),
    ).fetchone()

    if row and row["start_date"] and row["end_date"]:
        start_date = datetime.fromisoformat(str(row["start_date"])).date() - timedelta(
            days=padding_days
        )
        # Brightspace treats the end of the query window as an upper boundary.
        end_date = datetime.fromisoformat(str(row["end_date"])).date() + timedelta(
            days=padding_days + 1
        )
    else:
        today = datetime.now(UTC).date()
        start_date = today - timedelta(days=120)
        end_date = today + timedelta(days=240)

    return (
        f"{start_date.isoformat()}T00:00:00Z",
        f"{end_date.isoformat()}T00:00:00Z",
    )
