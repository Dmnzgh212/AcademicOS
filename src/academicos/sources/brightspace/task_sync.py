from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

from academicos.calendar.models import SourceType
from academicos.sources.store import source_item_id

TASK_NAMESPACE = UUID("e55ac2c6-9795-43d4-b890-0e7bfab1d1a8")

_DEFAULTS = {
    "assignment": {"estimate": 90, "importance": 0.60},
    "quiz": {"estimate": 45, "importance": 0.70},
}


@dataclass(frozen=True)
class TaskSyncReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0

    def as_dataset(self) -> dict[str, int]:
        return {
            "fetched": self.created + self.updated + self.unchanged + self.skipped,
            "changed": self.created + self.updated,
            "unchanged": self.unchanged + self.skipped,
        }


def _records(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("Objects", "Items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _external_id(record: dict[str, Any], kind: str) -> str | None:
    keys = ("Id", "Identifier", "ObjectId")
    if kind == "quiz":
        keys += ("QuizId",)
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _title(record: dict[str, Any], kind: str, external_id: str) -> str:
    for key in ("Name", "Title", "Subject"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return f"{kind.title()} {external_id}"


def _due_at(record: dict[str, Any]) -> datetime | None:
    for key in ("DueDate", "EndDate"):
        parsed = _parse_datetime(record.get(key))
        if parsed is not None:
            return parsed
    return None


def _task_id(course_id: str, kind: str, org_unit_id: str | int, external_id: str) -> str:
    return str(uuid5(TASK_NAMESPACE, f"{course_id}|{kind}|{org_unit_id}|{external_id}"))


def _source_key(org_unit_id: str | int, dataset: str, external_id: str) -> str:
    return f"{org_unit_id}:{dataset}:{external_id}"


def _upsert_one(
    conn: sqlite3.Connection,
    *,
    course_id: str,
    org_unit_id: str | int,
    dataset: str,
    kind: str,
    record: dict[str, Any],
    seen_at: datetime,
) -> str:
    if record.get("IsHidden") is True:
        return "skipped"

    external_id = _external_id(record, kind)
    if external_id is None:
        return "skipped"

    source_key = _source_key(org_unit_id, dataset, external_id)
    link = conn.execute(
        "SELECT task_id FROM task_source_links WHERE source_type = ? AND source_key = ?",
        (SourceType.BRIGHTSPACE.value, source_key),
    ).fetchone()
    task_id = link["task_id"] if link is not None else _task_id(
        course_id, kind, org_unit_id, external_id
    )

    title = _title(record, kind, external_id)
    due_at = _due_at(record)
    due_value = due_at.isoformat() if due_at else None
    defaults = _DEFAULTS[kind]
    existing = conn.execute(
        """
        SELECT title, course_id, task_type, due_at
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    if existing is None:
        conn.execute(
            """
            INSERT INTO tasks(
                id, course_id, title, task_type, due_at,
                initial_estimate_minutes, remaining_minutes,
                importance, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                task_id,
                course_id,
                title,
                kind,
                due_value,
                defaults["estimate"],
                defaults["estimate"],
                defaults["importance"],
            ),
        )
        result = "created"
    else:
        changed = any(
            (
                existing["title"] != title,
                existing["course_id"] != course_id,
                existing["task_type"] != kind,
                existing["due_at"] != due_value,
            )
        )
        if changed:
            conn.execute(
                """
                UPDATE tasks
                SET course_id = ?, title = ?, task_type = ?, due_at = ?
                WHERE id = ?
                """,
                (course_id, title, kind, due_value, task_id),
            )
            result = "updated"
        else:
            result = "unchanged"

    source_item_key = source_item_id(SourceType.BRIGHTSPACE, source_key)
    conn.execute(
        """
        INSERT INTO task_source_links(
            source_type, source_key, task_id, source_item_id,
            source_kind, external_id, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_type, source_key) DO UPDATE SET
            task_id = excluded.task_id,
            source_item_id = excluded.source_item_id,
            source_kind = excluded.source_kind,
            external_id = excluded.external_id,
            last_seen_at = excluded.last_seen_at
        """,
        (
            SourceType.BRIGHTSPACE.value,
            source_key,
            task_id,
            source_item_key,
            kind,
            external_id,
            seen_at.astimezone(UTC).isoformat(),
        ),
    )
    return result


def reconcile_brightspace_tasks(
    conn: sqlite3.Connection,
    *,
    course_id: str,
    org_unit_id: str | int,
    assignments: object | None,
    quizzes: object | None,
    seen_at: datetime | None = None,
) -> TaskSyncReport:
    """Create/update local Tasks from authoritative structured Brightspace objects."""
    seen_at = seen_at or datetime.now(UTC)
    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}

    with conn:
        for dataset, kind, payload in (
            ("assignments", "assignment", assignments),
            ("quizzes", "quiz", quizzes),
        ):
            for record in _records(payload):
                outcome = _upsert_one(
                    conn,
                    course_id=course_id,
                    org_unit_id=org_unit_id,
                    dataset=dataset,
                    kind=kind,
                    record=record,
                    seen_at=seen_at,
                )
                counts[outcome] += 1

    return TaskSyncReport(**counts)
