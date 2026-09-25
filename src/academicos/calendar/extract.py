from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

from academicos.calendar.models import CandidateEvent, EventKind, SessionType

EXTRACT_NAMESPACE = UUID("8c45d54c-5c91-45f0-a311-8478fa2a95f8")

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_SESSION_WORDS = {
    "lecture": SessionType.LECTURE,
    "lab": SessionType.LAB,
    "tutorial": SessionType.TUTORIAL,
    "dgd": SessionType.DGD,
}

_CANCELLATION_RE = re.compile(
    r"\b(?:no\s+(?:class|lecture|lab|tutorial|dgd)|"
    r"(?:class|lecture|lab|tutorial|dgd)\s+(?:is|has\s+been|will\s+be)\s+cancel(?:l)?ed|"
    r"cancel(?:l)?ed\s+(?:class|lecture|lab|tutorial|dgd))\b",
    re.IGNORECASE,
)

_ONLINE_RE = re.compile(
    r"\b(?:meet(?:ing)?|held|class|lecture|lab|tutorial|dgd|session|we\s+will\s+meet)"
    r".{0,60}\b(?:online|zoom|remotely|remote)\b",
    re.IGNORECASE | re.DOTALL,
)

_LOCATION_RE = re.compile(
    r"\b(?:room|location)\s+(?:has\s+)?(?:been\s+)?(?:changed|moved)\s+to\s+"
    r"(?P<location>[^.;\n]{2,60})",
    re.IGNORECASE,
)

_DEADLINE_RE = re.compile(
    r"\b(?:deadline|due\s+date|due)\b.{0,100}\b(?:extended|moved|changed)\b",
    re.IGNORECASE | re.DOTALL,
)

_NEW_MATERIAL_RE = re.compile(
    r"\b(?:slides?|notes?|recording|module|lecture\s+material|practice\s+material)\b"
    r".{0,100}\b(?:posted|uploaded|available|released)\b|"
    r"\b(?:posted|uploaded|released)\b.{0,100}\b(?:slides?|notes?|recording|module|materials?)\b",
    re.IGNORECASE | re.DOTALL,
)


def _local_published(published_at: datetime, timezone_name: str) -> datetime:
    tz = ZoneInfo(timezone_name)
    if published_at.tzinfo is None:
        return published_at.replace(tzinfo=tz)
    return published_at.astimezone(tz)


def _next_weekday(base: date, weekday: int, *, force_next: bool) -> date:
    delta = (weekday - base.weekday()) % 7
    if force_next and delta == 0:
        delta = 7
    return base + timedelta(days=delta)


def resolve_event_date(
    text: str,
    published_at: datetime,
    *,
    timezone_name: str = "America/Toronto",
) -> date | None:
    """Resolve simple academic date language relative to publication time."""
    local = _local_published(published_at, timezone_name)
    lowered = text.lower()

    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso_match:
        return date.fromisoformat(iso_match.group(1))

    if re.search(r"\btomorrow\b", lowered):
        return local.date() + timedelta(days=1)
    if re.search(r"\btoday\b", lowered):
        return local.date()

    next_weekday = re.search(
        r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        lowered,
    )
    if next_weekday:
        return _next_weekday(
            local.date(),
            _WEEKDAYS[next_weekday.group(1)],
            force_next=True,
        )

    weekday = re.search(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        lowered,
    )
    if weekday:
        return _next_weekday(
            local.date(),
            _WEEKDAYS[weekday.group(1)],
            force_next=False,
        )

    month_match = re.search(
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s+\d{1,2}(?:,?\s+20\d{2})?\b",
        text,
        re.IGNORECASE,
    )
    if month_match:
        parsed = date_parser.parse(month_match.group(0), default=local.replace(tzinfo=None))
        return parsed.date()

    return None


def _find_time(text: str) -> time | None:
    twelve = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b", text, re.I)
    if twelve:
        hour = int(twelve.group(1)) % 12
        minute = int(twelve.group(2) or 0)
        if twelve.group(3).lower().startswith("p"):
            hour += 12
        return time(hour, minute)

    twenty_four = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if twenty_four:
        return time(int(twenty_four.group(1)), int(twenty_four.group(2)))
    return None


def _session_hint(text: str) -> SessionType | None:
    lowered = text.lower()
    for word, session_type in _SESSION_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            return session_type
    return None


def resolve_target_session(
    conn: sqlite3.Connection,
    *,
    course_id: str,
    occurrence_date: date,
    text: str,
) -> str | None:
    rows = conn.execute(
        """
        SELECT id, session_type
        FROM course_sessions
        WHERE course_id = ?
          AND start_date <= ?
          AND end_date >= ?
          AND weekday = ?
        ORDER BY start_time
        """,
        (
            course_id,
            occurrence_date.isoformat(),
            occurrence_date.isoformat(),
            occurrence_date.weekday(),
        ),
    ).fetchall()

    hint = _session_hint(text)
    if hint is not None:
        rows = [row for row in rows if row["session_type"] == hint.value]

    if len(rows) == 1:
        return rows[0]["id"]
    return None


def _candidate_id(
    *,
    source_item_id: str,
    content_hash: str,
    kind: EventKind,
    target_ref: str | None,
    payload: dict,
) -> str:
    payload_key = "|".join(f"{key}={payload[key]}" for key in sorted(payload))
    return str(
        uuid5(
            EXTRACT_NAMESPACE,
            f"{source_item_id}|{content_hash}|{kind.value}|{target_ref or ''}|{payload_key}",
        )
    )


def _effective_at_for_date(day: date | None, published_at: datetime) -> datetime:
    if day is None:
        return published_at
    tzinfo = published_at.tzinfo
    return datetime.combine(day, time.min, tzinfo=tzinfo)


def _class_candidate(
    conn: sqlite3.Connection,
    *,
    kind: EventKind,
    source_item_id: str,
    content_hash: str,
    course_id: str,
    text: str,
    published_at: datetime,
    payload_extra: dict | None = None,
    base_confidence: float,
    timezone_name: str,
) -> CandidateEvent:
    occurrence_date = resolve_event_date(text, published_at, timezone_name=timezone_name)
    target_ref = None
    if occurrence_date is not None:
        target_ref = resolve_target_session(
            conn,
            course_id=course_id,
            occurrence_date=occurrence_date,
            text=text,
        )

    payload = dict(payload_extra or {})
    if occurrence_date is not None:
        payload["occurrence_date"] = occurrence_date.isoformat()

    confidence = base_confidence
    if occurrence_date is None:
        confidence -= 0.18
    if target_ref is None:
        confidence -= 0.12
    confidence = max(0.0, min(1.0, confidence))

    return CandidateEvent(
        id=_candidate_id(
            source_item_id=source_item_id,
            content_hash=content_hash,
            kind=kind,
            target_ref=target_ref,
            payload=payload,
        ),
        kind=kind,
        course_id=course_id,
        target_ref=target_ref,
        effective_at=_effective_at_for_date(occurrence_date, published_at),
        payload=payload,
        confidence=confidence,
    )


def _deadline_candidate(
    *,
    source_item_id: str,
    content_hash: str,
    course_id: str,
    text: str,
    title: str,
    published_at: datetime,
    timezone_name: str,
) -> CandidateEvent | None:
    if not _DEADLINE_RE.search(text):
        return None

    due_date = resolve_event_date(text, published_at, timezone_name=timezone_name)
    if due_date is None:
        return None
    due_time = _find_time(text) or time(23, 59)
    tz = ZoneInfo(timezone_name)
    due_at = datetime.combine(due_date, due_time, tzinfo=tz)
    payload = {
        "due_at": due_at.isoformat(),
        "announcement_title": title,
    }
    kind = EventKind.DEADLINE_CHANGED
    return CandidateEvent(
        id=_candidate_id(
            source_item_id=source_item_id,
            content_hash=content_hash,
            kind=kind,
            target_ref=None,
            payload=payload,
        ),
        kind=kind,
        course_id=course_id,
        effective_at=due_at,
        payload=payload,
        confidence=0.92,
    )


def extract_candidates_from_text(
    conn: sqlite3.Connection,
    *,
    source_item_id: str,
    content_hash: str,
    course_id: str,
    title: str,
    text: str,
    published_at: datetime,
    timezone_name: str = "America/Toronto",
) -> list[CandidateEvent]:
    """Extract conservative, deterministic academic candidates from trusted source text."""
    candidates: list[CandidateEvent] = []
    combined = f"{title}\n{text}".strip()

    if _CANCELLATION_RE.search(combined):
        candidates.append(
            _class_candidate(
                conn,
                kind=EventKind.CLASS_CANCELLED,
                source_item_id=source_item_id,
                content_hash=content_hash,
                course_id=course_id,
                text=combined,
                published_at=published_at,
                base_confidence=0.99,
                timezone_name=timezone_name,
            )
        )

    if _ONLINE_RE.search(combined):
        candidates.append(
            _class_candidate(
                conn,
                kind=EventKind.CLASS_MODE_CHANGED,
                source_item_id=source_item_id,
                content_hash=content_hash,
                course_id=course_id,
                text=combined,
                published_at=published_at,
                payload_extra={"new_delivery_mode": "online"},
                base_confidence=0.97,
                timezone_name=timezone_name,
            )
        )

    location_match = _LOCATION_RE.search(combined)
    if location_match:
        candidates.append(
            _class_candidate(
                conn,
                kind=EventKind.CLASS_LOCATION_CHANGED,
                source_item_id=source_item_id,
                content_hash=content_hash,
                course_id=course_id,
                text=combined,
                published_at=published_at,
                payload_extra={"new_location": location_match.group("location").strip()},
                base_confidence=0.96,
                timezone_name=timezone_name,
            )
        )

    deadline = _deadline_candidate(
        source_item_id=source_item_id,
        content_hash=content_hash,
        course_id=course_id,
        text=combined,
        title=title,
        published_at=published_at,
        timezone_name=timezone_name,
    )
    if deadline is not None:
        candidates.append(deadline)

    lowered = combined.lower()
    event_date = resolve_event_date(combined, published_at, timezone_name=timezone_name)
    if event_date is not None and re.search(r"\b(?:midterm|exam|final)\b", lowered):
        payload = {"date": event_date.isoformat(), "announcement_title": title}
        kind = EventKind.EXAM_ANNOUNCED
        candidates.append(
            CandidateEvent(
                id=_candidate_id(
                    source_item_id=source_item_id,
                    content_hash=content_hash,
                    kind=kind,
                    target_ref=None,
                    payload=payload,
                ),
                kind=kind,
                course_id=course_id,
                effective_at=_effective_at_for_date(event_date, published_at),
                payload=payload,
                confidence=0.94,
            )
        )
    elif event_date is not None and re.search(r"\bquiz\b", lowered):
        payload = {"date": event_date.isoformat(), "announcement_title": title}
        kind = EventKind.QUIZ_ANNOUNCED
        candidates.append(
            CandidateEvent(
                id=_candidate_id(
                    source_item_id=source_item_id,
                    content_hash=content_hash,
                    kind=kind,
                    target_ref=None,
                    payload=payload,
                ),
                kind=kind,
                course_id=course_id,
                effective_at=_effective_at_for_date(event_date, published_at),
                payload=payload,
                confidence=0.94,
            )
        )

    if _NEW_MATERIAL_RE.search(combined):
        payload = {"announcement_title": title}
        kind = EventKind.NEW_MATERIAL
        candidates.append(
            CandidateEvent(
                id=_candidate_id(
                    source_item_id=source_item_id,
                    content_hash=content_hash,
                    kind=kind,
                    target_ref=None,
                    payload=payload,
                ),
                kind=kind,
                course_id=course_id,
                effective_at=published_at,
                payload=payload,
                confidence=0.98,
            )
        )

    return candidates
