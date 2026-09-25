from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

CORE_BRIGHTSPACE_ENDPOINTS = frozenset(
    {
        "announcements",
        "assignments",
        "quizzes",
        "content",
        "content_structure",
        "grades",
        "grade_objects",
        "final_grade",
        "calendar",
        "due",
        "overdue",
        "updates",
        "discussions",
        "checklists",
        "overview",
    }
)


@dataclass(frozen=True)
class CoverageRow:
    source_key: str
    label: str
    supported: int
    blocked: int
    attention: int
    unknown: int
    total: int

    @property
    def coverage(self) -> float:
        return self.supported / self.total if self.total else 0.0


def _health_labels(conn: sqlite3.Connection) -> dict[str, str]:
    labels: dict[str, str] = {}
    rows = conn.execute(
        "SELECT source_key, metadata_json FROM source_health WHERE source_key LIKE 'brightspace:%'"
    ).fetchall()
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(metadata, dict) or metadata.get("org_id") is None:
            continue
        capability_key = f"brightspace:{metadata['org_id']}"
        labels[capability_key] = str(row["source_key"]).removeprefix("brightspace:")
    return labels


def brightspace_coverage(conn: sqlite3.Connection) -> list[CoverageRow]:
    rows = conn.execute(
        """
        SELECT source_key, endpoint, status
        FROM endpoint_capabilities
        WHERE source_key LIKE 'brightspace:%'
        ORDER BY source_key, endpoint
        """
    ).fetchall()
    labels = _health_labels(conn)
    grouped: dict[str, dict[str, str]] = {}
    for row in rows:
        endpoint = str(row["endpoint"])
        if endpoint not in CORE_BRIGHTSPACE_ENDPOINTS:
            continue
        grouped.setdefault(str(row["source_key"]), {})[endpoint] = str(row["status"])

    result: list[CoverageRow] = []
    for source_key, states in sorted(grouped.items()):
        supported = sum(state == "supported" for state in states.values())
        blocked = sum(state in {"unsupported", "forbidden"} for state in states.values())
        attention = sum(state in {"auth_error", "transient", "error"} for state in states.values())
        unknown = len(CORE_BRIGHTSPACE_ENDPOINTS - states.keys())
        result.append(
            CoverageRow(
                source_key=source_key,
                label=labels.get(source_key, source_key.removeprefix("brightspace:")),
                supported=supported,
                blocked=blocked,
                attention=attention,
                unknown=unknown,
                total=len(CORE_BRIGHTSPACE_ENDPOINTS),
            )
        )
    return result
