from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any


def _norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


@dataclass(frozen=True)
class CourseMapping:
    local_course_id: str
    code: str
    section: str | None
    org_unit_id: str
    brightspace_code: str | None
    brightspace_name: str | None


@dataclass(frozen=True)
class DiscoveryReport:
    mappings: tuple[CourseMapping, ...]
    unmatched_local: tuple[str, ...]
    ambiguous_local: dict[str, tuple[str, ...]]


def _course_offerings(enrollments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for enrollment in enrollments:
        org = enrollment.get("OrgUnit")
        if not isinstance(org, dict):
            continue
        type_info = org.get("Type")
        type_name = type_info.get("Name") if isinstance(type_info, dict) else None
        if type_name == "Course Offering":
            result.append(enrollment)
    return result


def discover_course_mappings(
    conn: sqlite3.Connection,
    enrollments: list[dict[str, Any]],
) -> DiscoveryReport:
    """Map local timetable courses to active Brightspace course offerings.

    Matching is intentionally conservative: the normalized local course code must
    appear in the Brightspace code or name. If a local section is known, it must
    also appear in the Brightspace code/name when multiple course-code matches exist.
    Ambiguous results are reported instead of guessed.
    """
    offerings = _course_offerings(enrollments)
    mappings: list[CourseMapping] = []
    unmatched: list[str] = []
    ambiguous: dict[str, tuple[str, ...]] = {}

    local_rows = conn.execute(
        "SELECT id, code, section FROM courses ORDER BY term DESC, code, COALESCE(section, '')"
    ).fetchall()

    for row in local_rows:
        local_code = _norm(row["code"])
        section = row["section"] or None
        local_label = str(row["code"]) + (f" {section}" if section else "")
        candidates: list[dict[str, Any]] = []

        for enrollment in offerings:
            org = enrollment["OrgUnit"]
            haystack = _norm(f"{org.get('Code', '')} {org.get('Name', '')}")
            if local_code and local_code in haystack:
                candidates.append(enrollment)

        if len(candidates) > 1 and section:
            section_norm = _norm(section)
            section_matches = []
            for enrollment in candidates:
                org = enrollment["OrgUnit"]
                haystack = _norm(f"{org.get('Code', '')} {org.get('Name', '')}")
                if section_norm and section_norm in haystack:
                    section_matches.append(enrollment)
            if section_matches:
                candidates = section_matches

        if len(candidates) == 1:
            org = candidates[0]["OrgUnit"]
            org_id = org.get("Id")
            if org_id is None:
                unmatched.append(local_label)
                continue
            mappings.append(
                CourseMapping(
                    local_course_id=row["id"],
                    code=row["code"],
                    section=section,
                    org_unit_id=str(org_id),
                    brightspace_code=str(org.get("Code")) if org.get("Code") is not None else None,
                    brightspace_name=str(org.get("Name")) if org.get("Name") is not None else None,
                )
            )
        elif not candidates:
            unmatched.append(local_label)
        else:
            options = []
            for enrollment in candidates:
                org = enrollment["OrgUnit"]
                options.append(
                    f"{org.get('Id')}:{org.get('Code') or ''}:{org.get('Name') or ''}"
                )
            ambiguous[local_label] = tuple(options)

    return DiscoveryReport(
        mappings=tuple(mappings),
        unmatched_local=tuple(unmatched),
        ambiguous_local=ambiguous,
    )
