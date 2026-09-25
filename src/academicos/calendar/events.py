from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid5

from academicos.calendar.models import (
    CandidateEvent,
    CandidateStatus,
    EventKind,
    OverrideKind,
)

EVENT_NAMESPACE = UUID("93020f12-c1de-49e7-8aa0-3e5467d5b8f7")


class CandidateTransitionError(RuntimeError):
    """Raised when a candidate cannot make the requested state transition."""


class CandidateConflictError(RuntimeError):
    """Raised when accepting a candidate would create an ambiguous truth override."""


@dataclass(frozen=True)
class AcceptanceResult:
    candidate_id: str
    status: CandidateStatus
    action_type: str
    action_id: str | None = None


def persist_candidate_event(
    conn: sqlite3.Connection,
    event: CandidateEvent,
    *,
    evidence_ids: tuple[str, ...] = (),
) -> None:
    """Persist an extracted candidate and optional evidence links idempotently."""
    with conn:
        conn.execute(
            """
            INSERT INTO candidate_events(
                id, kind, course_id, target_ref, effective_at,
                payload_json, confidence, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind=excluded.kind,
                course_id=excluded.course_id,
                target_ref=excluded.target_ref,
                effective_at=excluded.effective_at,
                payload_json=excluded.payload_json,
                confidence=excluded.confidence
            """,
            (
                event.id,
                event.kind.value,
                event.course_id,
                event.target_ref,
                event.effective_at.isoformat() if event.effective_at else None,
                json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
                event.confidence,
                event.status.value,
            ),
        )
        for evidence_id in evidence_ids:
            conn.execute(
                """
                INSERT OR IGNORE INTO candidate_evidence(candidate_event_id, evidence_id)
                VALUES (?, ?)
                """,
                (event.id, evidence_id),
            )


def _candidate_row(conn: sqlite3.Connection, candidate_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM candidate_events WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown candidate event: {candidate_id}")
    return row


def _payload(row: sqlite3.Row) -> dict:
    return json.loads(row["payload_json"] or "{}")


def _occurrence_date(row: sqlite3.Row, payload: dict) -> date:
    raw = payload.get("occurrence_date")
    if raw:
        return date.fromisoformat(raw)
    if row["effective_at"]:
        return datetime.fromisoformat(row["effective_at"]).date()
    raise ValueError(
        f"candidate {row['id']} requires payload.occurrence_date or effective_at"
    )


def _override_kind(event_kind: EventKind) -> OverrideKind:
    mapping = {
        EventKind.CLASS_CANCELLED: OverrideKind.CANCELLED,
        EventKind.CLASS_MOVED: OverrideKind.MOVED,
        EventKind.CLASS_MODE_CHANGED: OverrideKind.MODE_CHANGED,
        EventKind.CLASS_LOCATION_CHANGED: OverrideKind.LOCATION_CHANGED,
    }
    try:
        return mapping[event_kind]
    except KeyError as exc:
        raise ValueError(f"{event_kind.value} is not a class override event") from exc


def _override_id(candidate_id: str) -> str:
    return str(uuid5(EVENT_NAMESPACE, f"override|{candidate_id}"))


def _deadline_change_id(candidate_id: str) -> str:
    return str(uuid5(EVENT_NAMESPACE, f"deadline|{candidate_id}"))


def _ensure_no_override_conflict(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    occurrence_date: date,
    kind: OverrideKind,
) -> None:
    row = conn.execute(
        """
        SELECT id, candidate_event_id
        FROM event_overrides
        WHERE session_id = ? AND effective_date = ? AND kind = ?
        LIMIT 1
        """,
        (session_id, occurrence_date.isoformat(), kind.value),
    ).fetchone()
    if row is not None:
        raise CandidateConflictError(
            f"an active {kind.value} override already exists for "
            f"{session_id} on {occurrence_date.isoformat()} (override {row['id']})"
        )


def _accept_class_override(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    event_kind: EventKind,
    payload: dict,
) -> AcceptanceResult:
    session_id = row["target_ref"]
    if not session_id:
        raise ValueError(f"candidate {row['id']} requires target_ref=session_id")

    occurrence_date = _occurrence_date(row, payload)
    kind = _override_kind(event_kind)
    _ensure_no_override_conflict(
        conn,
        session_id=session_id,
        occurrence_date=occurrence_date,
        kind=kind,
    )

    values = {
        "new_start_at": None,
        "new_end_at": None,
        "new_location": None,
        "new_delivery_mode": None,
    }

    if event_kind == EventKind.CLASS_MOVED:
        values["new_start_at"] = payload.get("new_start_at")
        values["new_end_at"] = payload.get("new_end_at")
        if not values["new_start_at"] or not values["new_end_at"]:
            raise ValueError("class_moved requires new_start_at and new_end_at")
    elif event_kind == EventKind.CLASS_LOCATION_CHANGED:
        values["new_location"] = payload.get("new_location")
        if not values["new_location"]:
            raise ValueError("class_location_changed requires new_location")
    elif event_kind == EventKind.CLASS_MODE_CHANGED:
        values["new_delivery_mode"] = payload.get("new_delivery_mode")
        if not values["new_delivery_mode"]:
            raise ValueError("class_mode_changed requires new_delivery_mode")

    override_id = _override_id(row["id"])
    conn.execute(
        """
        INSERT INTO event_overrides(
            id, session_id, effective_date, kind,
            new_start_at, new_end_at, new_location, new_delivery_mode,
            candidate_event_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            override_id,
            session_id,
            occurrence_date.isoformat(),
            kind.value,
            values["new_start_at"],
            values["new_end_at"],
            values["new_location"],
            values["new_delivery_mode"],
            row["id"],
        ),
    )
    return AcceptanceResult(
        candidate_id=row["id"],
        status=CandidateStatus.ACCEPTED,
        action_type="event_override",
        action_id=override_id,
    )


def _accept_deadline_change(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    payload: dict,
) -> AcceptanceResult:
    task_id = row["target_ref"]
    if not task_id:
        raise ValueError(f"candidate {row['id']} requires target_ref=task_id")
    raw_due_at = payload.get("due_at")
    if not isinstance(raw_due_at, str) or not raw_due_at.strip():
        raise ValueError("deadline_changed requires payload.due_at")
    try:
        new_due_at = datetime.fromisoformat(raw_due_at).isoformat()
    except ValueError as exc:
        raise ValueError("deadline_changed payload.due_at must be ISO-8601") from exc

    task = conn.execute(
        "SELECT id, course_id, due_at FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    if task is None:
        raise ValueError(f"deadline target task does not exist: {task_id}")
    if row["course_id"] and task["course_id"] != row["course_id"]:
        raise ValueError("deadline target task belongs to a different course")

    change_id = _deadline_change_id(row["id"])
    conn.execute(
        """
        INSERT INTO task_deadline_changes(
            id, task_id, candidate_event_id, old_due_at, new_due_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (change_id, task_id, row["id"], task["due_at"], new_due_at),
    )
    conn.execute(
        "UPDATE tasks SET due_at = ? WHERE id = ?",
        (new_due_at, task_id),
    )
    return AcceptanceResult(
        candidate_id=row["id"],
        status=CandidateStatus.ACCEPTED,
        action_type="task_deadline_update",
        action_id=change_id,
    )


def accept_candidate_event(
    conn: sqlite3.Connection,
    candidate_id: str,
    *,
    automatic: bool = False,
    auto_threshold: float = 0.95,
) -> AcceptanceResult:
    """Accept one candidate and materialize its deterministic action."""
    with conn:
        row = _candidate_row(conn, candidate_id)
        current = CandidateStatus(row["status"])
        if current in {
            CandidateStatus.ACCEPTED,
            CandidateStatus.AUTO_ACCEPTED,
            CandidateStatus.REJECTED,
        }:
            raise CandidateTransitionError(
                f"candidate {candidate_id} is already {current.value}"
            )
        if automatic and row["confidence"] < auto_threshold:
            raise CandidateTransitionError(
                f"candidate {candidate_id} confidence {row['confidence']:.3f} "
                f"is below auto threshold {auto_threshold:.3f}"
            )

        event_kind = EventKind(row["kind"])
        payload = _payload(row)

        if event_kind in {
            EventKind.CLASS_CANCELLED,
            EventKind.CLASS_MOVED,
            EventKind.CLASS_MODE_CHANGED,
            EventKind.CLASS_LOCATION_CHANGED,
        }:
            result = _accept_class_override(conn, row, event_kind, payload)
        elif event_kind == EventKind.DEADLINE_CHANGED:
            result = _accept_deadline_change(conn, row, payload)
        else:
            raise NotImplementedError(
                f"acceptance materialization for {event_kind.value} is not implemented yet"
            )

        next_status = (
            CandidateStatus.AUTO_ACCEPTED if automatic else CandidateStatus.ACCEPTED
        )
        conn.execute(
            "UPDATE candidate_events SET status = ? WHERE id = ?",
            (next_status.value, candidate_id),
        )
        return AcceptanceResult(
            candidate_id=result.candidate_id,
            status=next_status,
            action_type=result.action_type,
            action_id=result.action_id,
        )


def reject_candidate_event(
    conn: sqlite3.Connection,
    candidate_id: str,
) -> AcceptanceResult:
    with conn:
        row = _candidate_row(conn, candidate_id)
        current = CandidateStatus(row["status"])
        if current in {CandidateStatus.ACCEPTED, CandidateStatus.AUTO_ACCEPTED}:
            raise CandidateTransitionError(
                f"accepted candidate {candidate_id} cannot be rejected without rollback"
            )
        if current == CandidateStatus.REJECTED:
            return AcceptanceResult(
                candidate_id=candidate_id,
                status=CandidateStatus.REJECTED,
                action_type="none",
            )

        conn.execute(
            "UPDATE candidate_events SET status = ? WHERE id = ?",
            (CandidateStatus.REJECTED.value, candidate_id),
        )
        return AcceptanceResult(
            candidate_id=candidate_id,
            status=CandidateStatus.REJECTED,
            action_type="none",
        )
