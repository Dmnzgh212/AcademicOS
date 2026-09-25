from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from academicos.calendar.inbox import CandidateInboxItem, list_candidate_inbox
from academicos.calendar.models import CandidateStatus
from academicos.calendar.truth import EffectiveSession, effective_sessions_for_date
from academicos.sources.run_ledger import latest_sync_run


@dataclass(frozen=True)
class BriefActivity:
    id: str
    kind: str
    title: str
    course_code: str | None
    occurred_at: datetime | None


@dataclass(frozen=True)
class BriefTask:
    id: str
    title: str
    course_code: str | None
    task_type: str
    due_at: datetime | None
    remaining_minutes: int
    importance: float
    status: str


@dataclass(frozen=True)
class BriefPlanBlock:
    id: str
    task_id: str
    task_title: str
    course_code: str | None
    start_at: datetime
    end_at: datetime
    state: str
    pinned: bool

    @property
    def minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)


@dataclass(frozen=True)
class MorningBrief:
    target_date: date
    sessions: tuple[EffectiveSession, ...]
    activities: tuple[BriefActivity, ...]
    pending_changes: tuple[CandidateInboxItem, ...]
    upcoming_tasks: tuple[BriefTask, ...]
    plan_blocks: tuple[BriefPlanBlock, ...]
    alerts: tuple[str, ...]


def _parse_local(value: str | None, tz: ZoneInfo) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _activities(
    conn: sqlite3.Connection,
    *,
    since: datetime,
    until: datetime,
    tz: ZoneInfo,
) -> list[BriefActivity]:
    rows = conn.execute(
        """
        SELECT af.id, af.kind, af.title, af.occurred_at, c.code AS course_code
        FROM activity_feed AS af
        LEFT JOIN courses AS c ON c.id = af.course_id
        WHERE af.occurred_at IS NOT NULL
          AND af.occurred_at >= ?
          AND af.occurred_at < ?
        ORDER BY af.occurred_at DESC
        """,
        (since.isoformat(), until.isoformat()),
    ).fetchall()
    return [
        BriefActivity(
            id=row["id"],
            kind=row["kind"],
            title=row["title"],
            course_code=row["course_code"],
            occurred_at=_parse_local(row["occurred_at"], tz),
        )
        for row in rows
    ]


def _tasks(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    horizon: datetime,
    tz: ZoneInfo,
) -> list[BriefTask]:
    rows = conn.execute(
        """
        SELECT t.*, c.code AS course_code
        FROM tasks AS t
        LEFT JOIN courses AS c ON c.id = t.course_id
        WHERE t.status IN ('pending', 'in_progress')
          AND t.progress < 1.0
          AND (t.due_at IS NULL OR t.due_at <= ?)
        ORDER BY
          CASE WHEN t.due_at IS NULL THEN 1 ELSE 0 END,
          t.due_at,
          t.importance DESC
        """,
        (horizon.isoformat(),),
    ).fetchall()

    tasks: list[BriefTask] = []
    for row in rows:
        due_at = _parse_local(row["due_at"], tz)
        if due_at is not None and due_at < now - timedelta(days=30):
            continue
        remaining = int(row["remaining_minutes"] or 0)
        if remaining <= 0:
            remaining = max(
                0,
                round(
                    int(row["initial_estimate_minutes"] or 0)
                    * (1.0 - float(row["progress"] or 0.0))
                ),
            )
        tasks.append(
            BriefTask(
                id=row["id"],
                title=row["title"],
                course_code=row["course_code"],
                task_type=row["task_type"],
                due_at=due_at,
                remaining_minutes=remaining,
                importance=float(row["importance"] or 0.5),
                status=row["status"],
            )
        )
    return tasks


def _plan_blocks(
    conn: sqlite3.Connection,
    *,
    start_at: datetime,
    end_at: datetime,
    tz: ZoneInfo,
) -> list[BriefPlanBlock]:
    rows = conn.execute(
        """
        SELECT
            pb.*,
            t.title AS task_title,
            c.code AS course_code
        FROM plan_blocks AS pb
        JOIN tasks AS t ON t.id = pb.task_id
        LEFT JOIN courses AS c ON c.id = t.course_id
        WHERE pb.start_at < ? AND pb.end_at > ?
          AND pb.state != 'skipped'
        ORDER BY pb.start_at
        """,
        (end_at.isoformat(), start_at.isoformat()),
    ).fetchall()
    blocks: list[BriefPlanBlock] = []
    for row in rows:
        block_start = _parse_local(row["start_at"], tz)
        block_end = _parse_local(row["end_at"], tz)
        if block_start is None or block_end is None:
            continue
        blocks.append(
            BriefPlanBlock(
                id=row["id"],
                task_id=row["task_id"],
                task_title=row["task_title"],
                course_code=row["course_code"],
                start_at=block_start,
                end_at=block_end,
                state=row["state"],
                pinned=bool(row["pinned"]),
            )
        )
    return blocks


def _alerts(
    *,
    target_date: date,
    now: datetime,
    tasks: list[BriefTask],
    plan_blocks: list[BriefPlanBlock],
    pending_changes: list[CandidateInboxItem],
) -> list[str]:
    alerts: list[str] = []
    if pending_changes:
        alerts.append(
            f"{len(pending_changes)} academic change(s) are waiting for review."
        )

    planned_by_task: dict[str, int] = {}
    for block in plan_blocks:
        planned_by_task[block.task_id] = planned_by_task.get(block.task_id, 0) + block.minutes

    for task in tasks:
        if task.due_at is None:
            continue
        hours_left = (task.due_at - now).total_seconds() / 3600
        if hours_left < 0:
            alerts.append(f"OVERDUE · {task.title}")
            continue
        if hours_left <= 48 and task.remaining_minutes > planned_by_task.get(task.id, 0):
            course = f"{task.course_code} · " if task.course_code else ""
            alerts.append(
                f"{course}{task.title} is due within 48h with "
                f"{task.remaining_minutes} min remaining."
            )

    total_today = sum(block.minutes for block in plan_blocks)
    if total_today >= 360:
        alerts.append(
            f"Heavy study day · {total_today // 60}h {total_today % 60}m planned."
        )
    if not alerts and target_date == now.date():
        alerts.append("No immediate academic risk detected from current local data.")
    return alerts


def _collection_alerts(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    tz: ZoneInfo,
) -> list[str]:
    latest = latest_sync_run(conn)
    if latest is None:
        return ["DATA UNKNOWN · no tracked source sync has completed yet."]

    status = str(latest["status"])
    finished_at = _parse_local(str(latest["finished_at"]), tz)
    when = finished_at.strftime("%H:%M") if finished_at else "unknown time"

    if status == "failed":
        return [f"DATA FAILED · latest source sync failed at {when}; source data may be incomplete."]
    if status == "partial":
        return [
            "DATA PARTIAL · latest sync finished with "
            f"{latest['partial_count']} partial and {latest['failed_count']} failed source(s)."
        ]
    if status == "empty":
        return ["DATA EMPTY · latest sync completed without any tracked source results."]
    if finished_at is not None:
        age = now - finished_at
        if age > timedelta(hours=2):
            hours = max(2, int(age.total_seconds() // 3600))
            return [f"DATA STALE · latest complete source sync is about {hours}h old."]
    return []


def build_morning_brief(
    conn: sqlite3.Connection,
    target_date: date,
    *,
    now: datetime | None = None,
    timezone_name: str = "America/Toronto",
    activity_lookback_hours: int = 24,
    task_horizon_days: int = 7,
) -> MorningBrief:
    """Build a deterministic daily brief from local AcademicOS state."""
    tz = ZoneInfo(timezone_name)
    local_now = now or datetime.now(tz)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=tz)
    else:
        local_now = local_now.astimezone(tz)

    day_start = datetime.combine(target_date, time.min, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    activity_until = min(day_end, local_now + timedelta(seconds=1)) if target_date == local_now.date() else day_end
    activity_since = activity_until - timedelta(hours=activity_lookback_hours)
    horizon = day_end + timedelta(days=task_horizon_days)

    sessions = effective_sessions_for_date(
        conn,
        target_date,
        timezone_name=timezone_name,
    )
    activities = _activities(
        conn,
        since=activity_since,
        until=activity_until,
        tz=tz,
    )
    pending_changes = list_candidate_inbox(
        conn,
        status=CandidateStatus.PENDING,
        limit=50,
    )
    tasks = _tasks(conn, now=local_now, horizon=horizon, tz=tz)
    plan_blocks = _plan_blocks(
        conn,
        start_at=day_start,
        end_at=day_end,
        tz=tz,
    )
    risk_alerts = _alerts(
        target_date=target_date,
        now=local_now,
        tasks=tasks,
        plan_blocks=plan_blocks,
        pending_changes=pending_changes,
    )
    collection_alerts = _collection_alerts(conn, now=local_now, tz=tz)
    if collection_alerts:
        risk_alerts = [
            alert for alert in risk_alerts if not alert.startswith("No immediate academic risk")
        ]
    alerts = collection_alerts + risk_alerts

    return MorningBrief(
        target_date=target_date,
        sessions=tuple(sessions),
        activities=tuple(activities),
        pending_changes=tuple(pending_changes),
        upcoming_tasks=tuple(tasks),
        plan_blocks=tuple(plan_blocks),
        alerts=tuple(alerts),
    )
