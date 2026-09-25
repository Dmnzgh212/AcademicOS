from __future__ import annotations

import sqlite3
from datetime import date, datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from academicos.calendar.models import OverrideKind, SessionType


class EffectiveSessionStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    MOVED = "moved"


class EffectiveSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    course_id: str
    course_code: str
    course_name: str
    course_section: str | None = None
    session_type: SessionType
    occurrence_date: date
    start_at: datetime
    end_at: datetime
    location: str | None = None
    delivery_mode: str | None = None
    status: EffectiveSessionStatus = EffectiveSessionStatus.SCHEDULED
    applied_override_ids: tuple[str, ...] = ()


def _parse_time(value: str) -> time:
    return time.fromisoformat(value)


def _parse_datetime(value: str | None, tz: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _base_datetime(day: date, value: str, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, _parse_time(value), tzinfo=tz)


def _base_occurs(row: sqlite3.Row, occurrence_date: date) -> bool:
    return (
        date.fromisoformat(row["start_date"]) <= occurrence_date <= date.fromisoformat(row["end_date"])
        and occurrence_date.weekday() == row["weekday"]
    )


def _session_row(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT
            s.*,
            c.code AS course_code,
            c.name AS course_name,
            c.section AS course_section
        FROM course_sessions AS s
        JOIN courses AS c ON c.id = s.course_id
        WHERE s.id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown recurring session: {session_id}")
    return row


def _overrides_for(
    conn: sqlite3.Connection,
    session_id: str,
    occurrence_date: date,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT rowid, *
        FROM event_overrides
        WHERE session_id = ? AND effective_date = ?
        ORDER BY rowid
        """,
        (session_id, occurrence_date.isoformat()),
    ).fetchall()


def _materialize_occurrence(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    occurrence_date: date,
    tz: ZoneInfo,
) -> EffectiveSession:
    start_at = _base_datetime(occurrence_date, row["start_time"], tz)
    end_at = _base_datetime(occurrence_date, row["end_time"], tz)
    location = row["location"]
    delivery_mode = row["delivery_mode"]
    status = EffectiveSessionStatus.SCHEDULED
    applied: list[str] = []

    for override in _overrides_for(conn, row["id"], occurrence_date):
        applied.append(override["id"])
        kind = OverrideKind(override["kind"])

        if kind == OverrideKind.CANCELLED:
            status = EffectiveSessionStatus.CANCELLED
        elif kind == OverrideKind.MOVED:
            new_start = _parse_datetime(override["new_start_at"], tz)
            new_end = _parse_datetime(override["new_end_at"], tz)
            if new_start is None or new_end is None:
                raise ValueError(
                    f"moved override {override['id']} must define new_start_at and new_end_at"
                )
            start_at = new_start
            end_at = new_end
            status = EffectiveSessionStatus.MOVED

        if override["new_location"] is not None:
            location = override["new_location"]
        if override["new_delivery_mode"] is not None:
            delivery_mode = override["new_delivery_mode"]

    return EffectiveSession(
        session_id=row["id"],
        course_id=row["course_id"],
        course_code=row["course_code"],
        course_name=row["course_name"],
        course_section=row["course_section"],
        session_type=SessionType(row["session_type"]),
        occurrence_date=occurrence_date,
        start_at=start_at,
        end_at=end_at,
        location=location,
        delivery_mode=delivery_mode,
        status=status,
        applied_override_ids=tuple(applied),
    )


def effective_sessions_for_date(
    conn: sqlite3.Connection,
    target_date: date,
    *,
    timezone_name: str = "America/Toronto",
    include_cancelled: bool = False,
) -> list[EffectiveSession]:
    """Return effective Truth Calendar sessions visible on one date."""
    tz = ZoneInfo(timezone_name)
    occurrence_keys: set[tuple[str, date]] = set()

    base_rows = conn.execute(
        """
        SELECT
            s.*,
            c.code AS course_code,
            c.name AS course_name,
            c.section AS course_section
        FROM course_sessions AS s
        JOIN courses AS c ON c.id = s.course_id
        WHERE s.start_date <= ? AND s.end_date >= ? AND s.weekday = ?
        """,
        (target_date.isoformat(), target_date.isoformat(), target_date.weekday()),
    ).fetchall()

    for row in base_rows:
        if _base_occurs(row, target_date):
            occurrence_keys.add((row["id"], target_date))

    moved_rows = conn.execute(
        """
        SELECT session_id, effective_date
        FROM event_overrides
        WHERE kind = ?
          AND new_start_at IS NOT NULL
          AND substr(new_start_at, 1, 10) = ?
        """,
        (OverrideKind.MOVED.value, target_date.isoformat()),
    ).fetchall()

    for moved in moved_rows:
        base_date = date.fromisoformat(moved["effective_date"])
        row = _session_row(conn, moved["session_id"])
        if _base_occurs(row, base_date):
            occurrence_keys.add((moved["session_id"], base_date))

    effective: list[EffectiveSession] = []
    for session_id, occurrence_date in occurrence_keys:
        row = _session_row(conn, session_id)
        item = _materialize_occurrence(conn, row, occurrence_date, tz)

        if item.start_at.astimezone(tz).date() != target_date:
            continue
        if item.status == EffectiveSessionStatus.CANCELLED and not include_cancelled:
            continue
        effective.append(item)

    effective.sort(key=lambda item: (item.start_at, item.course_code, item.session_type.value))
    return effective
