from __future__ import annotations

import sqlite3
from typing import Any

import requests

from academicos.sources.brightspace.client import BrightspaceClient
from academicos.sources.brightspace.collector import CollectionReport, collect_course_data
from academicos.sources.capabilities import record_failure, record_success, should_probe

DEFAULT_DATASETS = {
    "announcements",
    "assignments",
    "submissions",
    "quizzes",
    "quiz_attempts",
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

_SUCCESS_DATASET = {
    "announcements": "announcements",
    "assignments": "assignments",
    "quizzes": "quizzes",
    "content": "content",
    "content_structure": "content_root",
    "grades": "grades",
    "grade_objects": "grade_objects",
    "final_grade": "final_grade",
    "calendar": "calendar",
    "due": "due",
    "overdue": "overdue",
    "updates": "updates",
    "discussions": "discussion_forums",
    "checklists": "checklists",
    "overview": "overview",
}

_ERROR_DATASET = {
    "content_structure": "content_root",
    "discussions": "discussion_forums",
}


def _http_error_from_text(text: str) -> requests.HTTPError | None:
    prefix = text.split(":", 1)[0].strip()
    if not prefix.isdigit():
        return None
    status = int(prefix)
    response = requests.Response()
    response.status_code = status
    response.url = "https://redacted.invalid/"
    return requests.HTTPError(f"HTTP {status}", response=response)


def collect_course_data_capability_aware(
    conn: sqlite3.Connection,
    client: BrightspaceClient,
    *,
    course_id: str,
    org_unit_id: str | int,
    since: str | None = None,
    start: str | None = None,
    end: str | None = None,
    include: set[str] | None = None,
    auto_accept_announcements: bool = False,
    timezone_name: str = "America/Toronto",
) -> CollectionReport:
    """Run the normal collector while cooling down known unavailable endpoints.

    Only top-level course capabilities are cached. Nested submissions, quiz attempts,
    content modules and discussion posts remain isolated by the base collector because
    their availability can differ item-by-item.
    """
    source_key = f"brightspace:{org_unit_id}"
    wanted = set(include if include is not None else DEFAULT_DATASETS)
    top_level = set(_SUCCESS_DATASET)
    skipped = {
        name
        for name in wanted & top_level
        if not should_probe(conn, source_key, name)
    }
    effective = wanted - skipped

    # The base collector historically treats an empty set as "use defaults".
    # If capability filtering removed every requested top-level endpoint, calling it
    # would accidentally re-enable all endpoints and defeat the cooldown.
    if effective:
        report = collect_course_data(
            conn,
            client,
            course_id=course_id,
            org_unit_id=org_unit_id,
            since=since,
            start=start,
            end=end,
            include=effective,
            auto_accept_announcements=auto_accept_announcements,
            timezone_name=timezone_name,
        )
    else:
        report = CollectionReport()

    for name in top_level & effective:
        dataset = _SUCCESS_DATASET[name]
        error_key = _ERROR_DATASET.get(name, name)
        if dataset in report.datasets:
            counts: dict[str, Any] = report.datasets[dataset]
            record_success(
                conn,
                source_key,
                name,
                {"collector": True, "fetched": counts.get("fetched", 0)},
            )
            continue
        error_text = report.errors.get(error_key)
        if error_text:
            error = _http_error_from_text(error_text)
            record_failure(
                conn,
                source_key,
                name,
                error or RuntimeError(error_text),
            )

    for name in sorted(skipped):
        report.datasets[f"skipped:{name}"] = {
            "fetched": 0,
            "changed": 0,
            "unchanged": 0,
        }

    return report
