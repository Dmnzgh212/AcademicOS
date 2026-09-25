from __future__ import annotations

import json
import sqlite3
from datetime import date, time
from pathlib import Path
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator

from academicos.calendar.models import SessionType

TIMETABLE_NAMESPACE = UUID("39ef1f6c-6485-4dcf-8d7c-fb6784383ae6")

DAY_ALIASES = {
    "MO": 0,
    "MON": 0,
    "MONDAY": 0,
    "TU": 1,
    "TUE": 1,
    "TUES": 1,
    "TUESDAY": 1,
    "WE": 2,
    "WED": 2,
    "WEDNESDAY": 2,
    "TH": 3,
    "THU": 3,
    "THUR": 3,
    "THURSDAY": 3,
    "FR": 4,
    "FRI": 4,
    "FRIDAY": 4,
    "SA": 5,
    "SAT": 5,
    "SATURDAY": 5,
    "SU": 6,
    "SUN": 6,
    "SUNDAY": 6,
}


class TimetableSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_type: SessionType
    days: list[int | str] = Field(min_length=1)
    start_time: time
    end_time: time
    start_date: date
    end_date: date
    location: str | None = None
    delivery_mode: str | None = None
    group: str | None = None
    key: str | None = None

    @field_validator("days", mode="before")
    @classmethod
    def normalize_days(cls, value: object) -> list[int]:
        if not isinstance(value, list):
            raise ValueError("days must be a list")
        normalized: list[int] = []
        for raw in value:
            if isinstance(raw, int):
                day = raw
            elif isinstance(raw, str):
                token = raw.strip().upper()
                if token not in DAY_ALIASES:
                    raise ValueError(f"unknown weekday: {raw}")
                day = DAY_ALIASES[token]
            else:
                raise ValueError(f"invalid weekday value: {raw!r}")
            if day < 0 or day > 6:
                raise ValueError(f"weekday out of range: {day}")
            if day not in normalized:
                normalized.append(day)
        return normalized


class TimetableCourseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    section: str | None = None
    sessions: list[TimetableSessionInput] = Field(default_factory=list)


class TimetableDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    timezone: str = "America/Toronto"
    courses: list[TimetableCourseInput]


def load_timetable(path: str | Path) -> TimetableDocument:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return TimetableDocument.model_validate(payload)


def _clean(value: str | None) -> str:
    return "" if value is None else value.strip()


def course_id_for(term: str, code: str, section: str | None) -> str:
    identity = f"course|{term.strip()}|{code.strip().upper()}|{_clean(section).upper()}"
    return str(uuid5(TIMETABLE_NAMESPACE, identity))


def session_id_for(
    *,
    course_id: str,
    session_type: SessionType,
    weekday: int,
    group: str | None,
    key: str | None,
    start_time: time,
) -> str:
    stable_component = _clean(key) or f"{session_type.value}|{_clean(group)}|{weekday}"
    if not key and not group:
        stable_component += f"|{start_time.isoformat(timespec='minutes')}"
    identity = f"session|{course_id}|{stable_component}"
    return str(uuid5(TIMETABLE_NAMESPACE, identity))


def import_timetable(
    conn: sqlite3.Connection,
    document: TimetableDocument,
) -> dict[str, int]:
    """Upsert a user-authoritative base timetable idempotently."""
    course_count = 0
    session_count = 0

    with conn:
        for course in document.courses:
            course_id = course_id_for(document.term, course.code, course.section)
            conn.execute(
                """
                INSERT INTO courses(id, code, name, term, section)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    code=excluded.code,
                    name=excluded.name,
                    term=excluded.term,
                    section=excluded.section
                """,
                (
                    course_id,
                    course.code.strip().upper(),
                    course.name.strip(),
                    document.term.strip(),
                    _clean(course.section) or None,
                ),
            )
            course_count += 1

            desired_session_ids: list[str] = []
            for session in course.sessions:
                for weekday in session.days:
                    assert isinstance(weekday, int)
                    session_id = session_id_for(
                        course_id=course_id,
                        session_type=session.session_type,
                        weekday=weekday,
                        group=session.group,
                        key=session.key,
                        start_time=session.start_time,
                    )
                    desired_session_ids.append(session_id)
                    conn.execute(
                        """
                        INSERT INTO course_sessions(
                            id, course_id, session_type, weekday,
                            start_time, end_time, start_date, end_date,
                            location, delivery_mode
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            course_id=excluded.course_id,
                            session_type=excluded.session_type,
                            weekday=excluded.weekday,
                            start_time=excluded.start_time,
                            end_time=excluded.end_time,
                            start_date=excluded.start_date,
                            end_date=excluded.end_date,
                            location=excluded.location,
                            delivery_mode=excluded.delivery_mode
                        """,
                        (
                            session_id,
                            course_id,
                            session.session_type.value,
                            weekday,
                            session.start_time.isoformat(timespec="minutes"),
                            session.end_time.isoformat(timespec="minutes"),
                            session.start_date.isoformat(),
                            session.end_date.isoformat(),
                            _clean(session.location) or None,
                            _clean(session.delivery_mode) or None,
                        ),
                    )
                    session_count += 1

            if desired_session_ids:
                placeholders = ",".join("?" for _ in desired_session_ids)
                conn.execute(
                    f"""
                    DELETE FROM course_sessions
                    WHERE course_id = ?
                      AND id NOT IN ({placeholders})
                    """,
                    [course_id, *desired_session_ids],
                )
            else:
                conn.execute(
                    "DELETE FROM course_sessions WHERE course_id = ?",
                    (course_id,),
                )

    return {"courses": course_count, "sessions": session_count}
