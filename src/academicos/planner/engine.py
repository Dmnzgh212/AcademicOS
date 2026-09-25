from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

from academicos.calendar.truth import effective_sessions_for_range
from academicos.planner.velocity import VelocityEstimate, estimate_velocity

PLANNER_NAMESPACE = UUID("d7e40a84-68dd-47dd-9cd0-6c946d94b60f")


@dataclass(frozen=True)
class FreeInterval:
    start_at: datetime
    end_at: datetime

    @property
    def minutes(self) -> int:
        return max(0, int((self.end_at - self.start_at).total_seconds() // 60))


@dataclass(frozen=True)
class PlanningTask:
    id: str
    course_id: str | None
    title: str
    task_type: str
    due_at: datetime | None
    remaining_minutes: int
    importance: float
    progress: float
    velocity: VelocityEstimate
    adjusted_minutes: int
    urgency: float


@dataclass(frozen=True)
class PlannedBlock:
    id: str
    task_id: str
    start_at: datetime
    end_at: datetime
    urgency: float
    planner_run_id: str


@dataclass(frozen=True)
class PlannerResult:
    planner_run_id: str
    blocks: tuple[PlannedBlock, ...]
    unscheduled_minutes: dict[str, int]


def _as_local(value: str | None, tz: ZoneInfo) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _subtract_interval(
    intervals: list[FreeInterval],
    busy_start: datetime,
    busy_end: datetime,
) -> list[FreeInterval]:
    result: list[FreeInterval] = []
    for interval in intervals:
        if busy_end <= interval.start_at or busy_start >= interval.end_at:
            result.append(interval)
            continue
        if busy_start > interval.start_at:
            result.append(FreeInterval(interval.start_at, busy_start))
        if busy_end < interval.end_at:
            result.append(FreeInterval(busy_end, interval.end_at))
    return [interval for interval in result if interval.minutes > 0]


def build_free_intervals(
    conn: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
    now: datetime,
    timezone_name: str = "America/Toronto",
    day_start: time = time(8, 0),
    day_end: time = time(23, 0),
    buffer_minutes: int = 10,
) -> list[FreeInterval]:
    tz = ZoneInfo(timezone_name)
    local_now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    truth = effective_sessions_for_range(
        conn,
        start_date,
        end_date,
        timezone_name=timezone_name,
    )

    intervals: list[FreeInterval] = []
    current = start_date
    while current <= end_date:
        start_at = datetime.combine(current, day_start, tzinfo=tz)
        end_at = datetime.combine(current, day_end, tzinfo=tz)
        if current == local_now.date() and local_now > start_at:
            rounded = local_now.replace(second=0, microsecond=0)
            start_at = rounded
        if start_at < end_at:
            day_intervals = [FreeInterval(start_at, end_at)]
            for session in truth.get(current, []):
                busy_start = session.start_at - timedelta(minutes=buffer_minutes)
                busy_end = session.end_at + timedelta(minutes=buffer_minutes)
                day_intervals = _subtract_interval(day_intervals, busy_start, busy_end)
            intervals.extend(day_intervals)
        current += timedelta(days=1)

    existing = conn.execute(
        """
        SELECT start_at, end_at
        FROM plan_blocks
        WHERE state IN ('started', 'completed') OR pinned = 1
        """
    ).fetchall()
    for row in existing:
        busy_start = _as_local(row["start_at"], tz)
        busy_end = _as_local(row["end_at"], tz)
        if busy_start and busy_end:
            intervals = _subtract_interval(intervals, busy_start, busy_end)

    intervals.sort(key=lambda interval: interval.start_at)
    return intervals


def _available_minutes_before(
    intervals: list[FreeInterval],
    due_at: datetime | None,
) -> int:
    total = 0
    for interval in intervals:
        end = interval.end_at if due_at is None else min(interval.end_at, due_at)
        if end > interval.start_at:
            total += int((end - interval.start_at).total_seconds() // 60)
    return total


def _deadline_pressure(now: datetime, due_at: datetime | None) -> float:
    if due_at is None:
        return 0.15
    hours = max(0.0, (due_at - now).total_seconds() / 3600)
    return 1.0 / (1.0 + hours / 24.0)


def _task_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE status IN ('pending', 'in_progress')
          AND progress < 1.0
          AND (remaining_minutes > 0 OR initial_estimate_minutes > 0)
        ORDER BY rowid
        """
    ).fetchall()


def load_planning_tasks(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    free_intervals: list[FreeInterval],
    timezone_name: str = "America/Toronto",
) -> list[PlanningTask]:
    tz = ZoneInfo(timezone_name)
    local_now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    tasks: list[PlanningTask] = []

    for row in _task_rows(conn):
        due_at = _as_local(row["due_at"], tz)
        base_remaining = int(row["remaining_minutes"] or 0)
        if base_remaining <= 0:
            base_remaining = math.ceil(
                int(row["initial_estimate_minutes"] or 0) * (1.0 - float(row["progress"] or 0.0))
            )
        if base_remaining <= 0:
            continue

        velocity = estimate_velocity(
            conn,
            course_id=row["course_id"],
            task_type=row["task_type"],
        )
        adjusted = max(1, math.ceil(base_remaining * velocity.multiplier))
        available = max(1, _available_minutes_before(free_intervals, due_at))
        workload_pressure = min(1.5, adjusted / available)
        deadline_pressure = _deadline_pressure(local_now, due_at)
        importance = float(row["importance"] or 0.5)
        urgency = (
            0.45 * min(1.0, workload_pressure)
            + 0.35 * deadline_pressure
            + 0.20 * importance
        )

        tasks.append(
            PlanningTask(
                id=row["id"],
                course_id=row["course_id"],
                title=row["title"],
                task_type=row["task_type"],
                due_at=due_at,
                remaining_minutes=base_remaining,
                importance=importance,
                progress=float(row["progress"] or 0.0),
                velocity=velocity,
                adjusted_minutes=adjusted,
                urgency=urgency,
            )
        )

    tasks.sort(
        key=lambda task: (
            -task.urgency,
            task.due_at or datetime.max.replace(tzinfo=tz),
            task.id,
        )
    )
    return tasks


def chunk_minutes(
    total_minutes: int,
    *,
    preferred_minutes: int = 90,
    min_minutes: int = 30,
    max_minutes: int = 120,
) -> list[int]:
    if total_minutes <= 0:
        return []
    if total_minutes <= max_minutes:
        return [total_minutes]

    count = max(1, math.ceil(total_minutes / preferred_minutes))
    while math.ceil(total_minutes / count) > max_minutes:
        count += 1

    base, remainder = divmod(total_minutes, count)
    chunks = [base + (1 if index < remainder else 0) for index in range(count)]

    if len(chunks) > 1 and chunks[-1] < min_minutes:
        deficit = min_minutes - chunks[-1]
        chunks[-2] -= deficit
        chunks[-1] += deficit
    return [chunk for chunk in chunks if chunk > 0]


def _place_chunk(
    intervals: list[FreeInterval],
    *,
    minutes: int,
    due_at: datetime | None,
) -> tuple[datetime, datetime] | None:
    duration = timedelta(minutes=minutes)
    for index, interval in enumerate(intervals):
        end_at = interval.start_at + duration
        hard_end = interval.end_at if due_at is None else min(interval.end_at, due_at)
        if end_at > hard_end:
            continue

        start_at = interval.start_at
        replacement: list[FreeInterval] = []
        if end_at < interval.end_at:
            replacement.append(FreeInterval(end_at, interval.end_at))
        intervals[index : index + 1] = replacement
        return start_at, end_at
    return None


def plan_tasks(
    conn: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
    now: datetime,
    timezone_name: str = "America/Toronto",
    persist: bool = True,
) -> PlannerResult:
    """Greedy adaptive planner inspired by Fluxure, Taskwarrior, and timeboxing tools."""
    planner_run_id = str(uuid4())
    free = build_free_intervals(
        conn,
        start_date=start_date,
        end_date=end_date,
        now=now,
        timezone_name=timezone_name,
    )
    tasks = load_planning_tasks(
        conn,
        now=now,
        free_intervals=free,
        timezone_name=timezone_name,
    )

    planned: list[PlannedBlock] = []
    unscheduled: dict[str, int] = {}

    for task in tasks:
        remaining = task.adjusted_minutes
        for chunk in chunk_minutes(task.adjusted_minutes):
            placement = _place_chunk(free, minutes=chunk, due_at=task.due_at)
            if placement is None:
                break
            start_at, end_at = placement
            block_id = str(
                uuid5(
                    PLANNER_NAMESPACE,
                    f"{planner_run_id}|{task.id}|{start_at.isoformat()}|{end_at.isoformat()}",
                )
            )
            planned.append(
                PlannedBlock(
                    id=block_id,
                    task_id=task.id,
                    start_at=start_at,
                    end_at=end_at,
                    urgency=task.urgency,
                    planner_run_id=planner_run_id,
                )
            )
            remaining -= chunk
        if remaining > 0:
            unscheduled[task.id] = remaining

    if persist:
        tz = ZoneInfo(timezone_name)
        window_start = datetime.combine(start_date, time.min, tzinfo=tz)
        window_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
        with conn:
            conn.execute(
                """
                DELETE FROM plan_blocks
                WHERE state = 'planned'
                  AND pinned = 0
                  AND start_at >= ?
                  AND start_at < ?
                """,
                (window_start.isoformat(), window_end.isoformat()),
            )
            conn.executemany(
                """
                INSERT INTO plan_blocks(
                    id, task_id, start_at, end_at, state, pinned, planner_run_id
                ) VALUES (?, ?, ?, ?, 'planned', 0, ?)
                """,
                [
                    (
                        block.id,
                        block.task_id,
                        block.start_at.isoformat(),
                        block.end_at.isoformat(),
                        block.planner_run_id,
                    )
                    for block in planned
                ],
            )

    return PlannerResult(
        planner_run_id=planner_run_id,
        blocks=tuple(planned),
        unscheduled_minutes=unscheduled,
    )
