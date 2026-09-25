from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class VelocityEstimate:
    multiplier: float
    samples: int
    scope: str


def _ratios(rows: list[sqlite3.Row]) -> list[float]:
    values: list[float] = []
    for row in rows:
        estimate = int(row["initial_estimate_minutes"] or 0)
        actual = int(row["actual_spent_minutes"] or 0)
        if estimate <= 0 or actual <= 0:
            continue
        values.append(actual / estimate)
    return values


def _shrunken_median(values: list[float]) -> float:
    """Shrink sparse personal-history estimates toward neutral 1.0."""
    if not values:
        return 1.0
    median = statistics.median(values)
    weight = len(values) / (len(values) + 3.0)
    adjusted = 1.0 + weight * (median - 1.0)
    return max(0.5, min(2.5, adjusted))


def estimate_velocity(
    conn: sqlite3.Connection,
    *,
    course_id: str | None,
    task_type: str | None,
    max_samples: int = 20,
) -> VelocityEstimate:
    """Estimate how long this user's work actually takes vs their own estimates."""
    scopes: list[tuple[str, str, tuple[object, ...]]] = []
    if course_id and task_type:
        scopes.append(
            (
                "course_task_type",
                "course_id = ? AND task_type = ?",
                (course_id, task_type),
            )
        )
    if course_id:
        scopes.append(("course", "course_id = ?", (course_id,)))
    scopes.append(("global", "1 = 1", ()))

    for scope, where_clause, params in scopes:
        rows = conn.execute(
            f"""
            SELECT initial_estimate_minutes, actual_spent_minutes
            FROM tasks
            WHERE {where_clause}
              AND initial_estimate_minutes > 0
              AND actual_spent_minutes > 0
              AND (status = 'done' OR progress >= 0.95)
            ORDER BY rowid DESC
            LIMIT ?
            """,
            (*params, max_samples),
        ).fetchall()
        values = _ratios(rows)
        minimum = 2 if scope != "global" else 1
        if len(values) >= minimum:
            return VelocityEstimate(
                multiplier=_shrunken_median(values),
                samples=len(values),
                scope=scope,
            )

    return VelocityEstimate(multiplier=1.0, samples=0, scope="default")
