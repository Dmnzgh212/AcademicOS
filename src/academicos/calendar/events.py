from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
    """Raised when a candidate action would overwrite newer or ambiguous truth."""


@dataclass(frozen=True)
class AcceptanceResult:
    candidate_id: str
    status: CandidateStatus
    action_type: str
    action_id: str | None = None


@dataclass(frozen=True)
class RollbackResult:
    candidate_id: str
    status: CandidateStatus
    action_type: str
    action_id: str | None = None
    restored_due_at: str | None = None
    reactivated_candidate_id: str | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _payload(row: sqlite3.Row) -> dict:
    return json.loads(row["payload_json"] or "{}")


def _deadline_payload_due(payload: dict) -> str | None:
    raw = payload.get("due_at")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def _supersede_pending_deadline_candidates(
    conn: sqlite3.Connection,
    event: CandidateEvent,
) -> None:
    if (
        event.kind != EventKind.DEADLINE_CHANGED
        or event.status != CandidateStatus.PENDING
        or not event.target_ref
    ):
        return

    new_due = _deadline_payload_due(event.payload)
    rows = conn.execute(
        """
        SELECT id, payload_json
        FROM candidate_events
        WHERE kind = ?
          AND target_ref = ?
          AND status = ?
          AND id <> ?
        """,
        (
            EventKind.DEADLINE_CHANGED.value,
            event.target_ref,
            CandidateStatus.PENDING.value,
            event.id,
        ),
    ).fetchall()
    now = _now_iso()
    for row in rows:
        old_due = _deadline_payload_due(json.loads(row["payload_json"] or "{}"))
        if old_due == new_due:
            continue
        conn.execute(
            """
            UPDATE candidate_events
            SET status = ?, superseded_by_candidate_id = ?, superseded_at = ?
            WHERE id = ? AND status = ?
            """,
            (
                CandidateStatus.SUPERSEDED.value,
                event.id,
                now,
                row["id"],
                CandidateStatus.PENDING.value,
            ),
        )


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
        _supersede_pending_deadline_candidates(conn, event)
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


def _active_deadline_change(
    conn: sqlite3.Connection,
    task_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM task_deadline_changes
        WHERE task_id = ? AND status = 'applied'
        ORDER BY applied_at DESC, id DESC
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()


def supersede_active_deadline_change(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    current_due_at: str | None,
    superseding_candidate_id: str | None = None,
) -> str | None:
    """Close the currently applied deadline change and return it only if chain-safe."""
    active = _active_deadline_change(conn, task_id)
    if active is None:
        return None

    now = _now_iso()
    conn.execute(
        """
        UPDATE task_deadline_changes
        SET status = 'superseded', superseded_at = ?
        WHERE id = ? AND status = 'applied'
        """,
        (now, active["id"]),
    )
    if active["candidate_event_id"]:
        conn.execute(
            """
            UPDATE candidate_events
            SET status = ?, superseded_by_candidate_id = ?, superseded_at = ?
            WHERE id = ? AND status IN (?, ?)
            """,
            (
                CandidateStatus.SUPERSEDED.value,
                superseding_candidate_id,
                now,
                active["candidate_event_id"],
                CandidateStatus.ACCEPTED.value,
                CandidateStatus.AUTO_ACCEPTED.value,
            ),
        )

    if active["new_due_at"] == current_due_at:
        return active["id"]
    return None


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

    supersedes_change_id = supersede_active_deadline_change(
        conn,
        task_id=task_id,
        current_due_at=task["due_at"],
        superseding_candidate_id=row["id"],
    )
    change_id = _deadline_change_id(row["id"])
    conn.execute(
        """
        INSERT INTO task_deadline_changes(
            id, task_id, candidate_event_id, old_due_at, new_due_at,
            status, supersedes_change_id
        ) VALUES (?, ?, ?, ?, ?, 'applied', ?)
        """,
        (
            change_id,
            task_id,
            row["id"],
            task["due_at"],
            new_due_at,
            supersedes_change_id,
        ),
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


def _reactivate_pending_predecessors(
    conn: sqlite3.Connection,
    candidate_id: str,
) -> None:
    """Restore directly superseded candidates that were never materialized."""
    rows = conn.execute(
        """
        SELECT ce.id
        FROM candidate_events AS ce
        WHERE ce.status = ?
          AND ce.superseded_by_candidate_id = ?
          AND NOT EXISTS (
              SELECT 1
              FROM task_deadline_changes AS tdc
              WHERE tdc.candidate_event_id = ce.id
          )
        """,
        (CandidateStatus.SUPERSEDED.value, candidate_id),
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            UPDATE candidate_events
            SET status = ?, superseded_by_candidate_id = NULL, superseded_at = NULL
            WHERE id = ?
            """,
            (CandidateStatus.PENDING.value, row["id"]),
        )


def _rollback_deadline_change(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
) -> RollbackResult:
    change = conn.execute(
        """
        SELECT *
        FROM task_deadline_changes
        WHERE candidate_event_id = ?
        ORDER BY applied_at DESC, id DESC
        LIMIT 1
        """,
        (row["id"],),
    ).fetchone()
    if change is None:
        raise CandidateTransitionError(
            f"candidate {row['id']} has no materialized deadline change"
        )
    if change["status"] != "applied":
        raise CandidateTransitionError(
            f"deadline change {change['id']} is {change['status']}, not applied"
        )

    task = conn.execute(
        "SELECT due_at FROM tasks WHERE id = ?",
        (change["task_id"],),
    ).fetchone()
    if task is None:
        raise CandidateConflictError(f"deadline target task no longer exists: {change['task_id']}")
    if task["due_at"] != change["new_due_at"]:
        raise CandidateConflictError(
            "task deadline changed after this candidate was applied; refusing to overwrite newer truth"
        )

    now = _now_iso()
    conn.execute(
        "UPDATE tasks SET due_at = ? WHERE id = ?",
        (change["old_due_at"], change["task_id"]),
    )
    conn.execute(
        """
        UPDATE task_deadline_changes
        SET status = 'rolled_back', rolled_back_at = ?
        WHERE id = ? AND status = 'applied'
        """,
        (now, change["id"]),
    )
    conn.execute(
        """
        UPDATE candidate_events
        SET status = ?, rolled_back_at = ?
        WHERE id = ?
        """,
        (CandidateStatus.ROLLED_BACK.value, now, row["id"]),
    )

    reactivated_candidate_id: str | None = None
    parent_id = change["supersedes_change_id"]
    if parent_id:
        parent = conn.execute(
            "SELECT * FROM task_deadline_changes WHERE id = ?",
            (parent_id,),
        ).fetchone()
        if (
            parent is not None
            and parent["status"] == "superseded"
            and parent["new_due_at"] == change["old_due_at"]
        ):
            conn.execute(
                """
                UPDATE task_deadline_changes
                SET status = 'applied', superseded_at = NULL
                WHERE id = ?
                """,
                (parent["id"],),
            )
            if parent["candidate_event_id"]:
                conn.execute(
                    """
                    UPDATE candidate_events
                    SET status = ?, superseded_by_candidate_id = NULL, superseded_at = NULL
                    WHERE id = ? AND status = ?
                    """,
                    (
                        CandidateStatus.ACCEPTED.value,
                        parent["candidate_event_id"],
                        CandidateStatus.SUPERSEDED.value,
                    ),
                )
                reactivated_candidate_id = parent["candidate_event_id"]

    if reactivated_candidate_id is None:
        _reactivate_pending_predecessors(conn, row["id"])

    return RollbackResult(
        candidate_id=row["id"],
        status=CandidateStatus.ROLLED_BACK,
        action_type="task_deadline_rollback",
        action_id=change["id"],
        restored_due_at=change["old_due_at"],
        reactivated_candidate_id=reactivated_candidate_id,
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
            CandidateStatus.SUPERSEDED,
            CandidateStatus.ROLLED_BACK,
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
            """
            UPDATE candidate_events
            SET status = ?, superseded_by_candidate_id = NULL,
                superseded_at = NULL, rolled_back_at = NULL
            WHERE id = ?
            """,
            (next_status.value, candidate_id),
        )
        return AcceptanceResult(
            candidate_id=result.candidate_id,
            status=next_status,
            action_type=result.action_type,
            action_id=result.action_id,
        )


def rollback_candidate_event(
    conn: sqlite3.Connection,
    candidate_id: str,
) -> RollbackResult:
    """Rollback the currently applied deterministic action for a reviewed candidate."""
    with conn:
        row = _candidate_row(conn, candidate_id)
        current = CandidateStatus(row["status"])
        if current not in {CandidateStatus.ACCEPTED, CandidateStatus.AUTO_ACCEPTED}:
            raise CandidateTransitionError(
                f"candidate {candidate_id} is {current.value}; only an applied candidate can be rolled back"
            )
        event_kind = EventKind(row["kind"])
        if event_kind == EventKind.DEADLINE_CHANGED:
            return _rollback_deadline_change(conn, row)
        raise NotImplementedError(
            f"rollback materialization for {event_kind.value} is not implemented yet"
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
        if current in {CandidateStatus.SUPERSEDED, CandidateStatus.ROLLED_BACK}:
            raise CandidateTransitionError(
                f"candidate {candidate_id} is {current.value} and cannot be rejected"
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
        _reactivate_pending_predecessors(conn, candidate_id)
        return AcceptanceResult(
            candidate_id=candidate_id,
            status=CandidateStatus.REJECTED,
            action_type="none",
        )
