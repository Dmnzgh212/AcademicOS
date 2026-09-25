from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from academicos.sources.brightspace.client import BrightspaceClient
from academicos.sources.brightspace.collector import persist_dataset
from academicos.sources.capabilities import record_failure, record_success, should_probe
from academicos.sources.mail.auth import acquire_graph_token
from academicos.sources.mail.graph import GraphMailClient
from academicos.sources.sync import (
    _brightspace_token,
    _course_specs,
    _open_db,
    _resolve_course_id,
    load_sync_config,
)


STAGED_BRIGHTSPACE_ENDPOINTS = (
    "announcements",
    "assignments",
    "quizzes",
    "content",
    "grades",
    "calendar",
    "updates",
)


@dataclass
class StagedSyncReport:
    changed: int = 0
    unchanged: int = 0
    courses_checked: int = 0
    endpoints_checked: int = 0
    endpoints_skipped: int = 0
    mail_probe_items: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    cursors_advanced: int = 0
    downloaded_files: int = 0


def _endpoint_fetchers(
    client: BrightspaceClient,
    org_id: str,
) -> dict[str, Callable[[], object]]:
    return {
        "announcements": lambda: client.news(org_id),
        "assignments": lambda: client.assignments(org_id),
        "quizzes": lambda: client.quizzes(org_id),
        "content": lambda: client.content_toc(org_id),
        "grades": lambda: client.grades(org_id),
        "calendar": lambda: client.calendar_events(org_id),
        "updates": lambda: client.updates(org_id),
    }


def stage_brightspace(
    conn: sqlite3.Connection,
    client: BrightspaceClient,
    *,
    brightspace: dict[str, Any],
) -> StagedSyncReport:
    """Validate Brightspace against real data without advancing cursors or downloading files.

    This deliberately stores raw source snapshots only. It does not run announcement-to-calendar
    candidate extraction, nested submissions/attempts/discussions, file mirroring, or sync-state
    cursor advancement. A later normal sync can therefore safely re-read the same material.
    """
    report = StagedSyncReport()
    try:
        enrollments = client.my_enrollments(active_only=True)
        for name, payload in (
            ("whoami", client.whoami()),
            ("enrollments", enrollments),
        ):
            result = persist_dataset(
                conn,
                dataset=name,
                payload=payload,
                course_id=None,
                org_unit_id=None,
            )
            report.changed += result["changed"]
            report.unchanged += result["unchanged"]
    except Exception as exc:
        report.errors["brightspace:account"] = f"{type(exc).__name__}: {exc}"
        return report

    courses, discovery_errors = _course_specs(conn, brightspace, enrollments)
    report.errors.update(discovery_errors)

    for course in courses:
        code = str(course["code"])
        section = str(course["section"]) if course.get("section") else None
        org_id = str(course["org_id"])
        label = code + (f"-{section}" if section else "")
        source_key = f"brightspace:{org_id}"
        try:
            course_id = _resolve_course_id(conn, code, section)
        except Exception as exc:
            report.errors[f"brightspace:{label}"] = f"{type(exc).__name__}: {exc}"
            continue

        report.courses_checked += 1
        for endpoint, fetcher in _endpoint_fetchers(client, org_id).items():
            if endpoint not in STAGED_BRIGHTSPACE_ENDPOINTS:
                continue
            if not should_probe(conn, source_key, endpoint):
                report.endpoints_skipped += 1
                continue
            try:
                payload = fetcher()
                result = persist_dataset(
                    conn,
                    dataset=endpoint,
                    payload=payload,
                    course_id=course_id,
                    org_unit_id=org_id,
                )
                report.changed += result["changed"]
                report.unchanged += result["unchanged"]
                report.endpoints_checked += 1
                record_success(conn, source_key, endpoint, payload)
            except Exception as exc:
                report.endpoints_checked += 1
                report.errors[f"brightspace:{label}:{endpoint}"] = (
                    f"{type(exc).__name__}: {exc}"
                )
                record_failure(conn, source_key, endpoint, exc)

    return report


def _merge(target: StagedSyncReport, source: StagedSyncReport) -> None:
    target.changed += source.changed
    target.unchanged += source.unchanged
    target.courses_checked += source.courses_checked
    target.endpoints_checked += source.endpoints_checked
    target.endpoints_skipped += source.endpoints_skipped
    target.mail_probe_items += source.mail_probe_items
    target.errors.update(source.errors)


def run_staged_sync(
    *,
    config_path: Path,
    db_path: Path | None = None,
    interactive_mail_auth: bool = False,
) -> StagedSyncReport:
    """Run a bounded first-sync validation against configured live sources.

    Invariants: no sync-state cursor is advanced and no course/mail attachment is downloaded.
    """
    config = load_sync_config(config_path)
    app_config = config.get("app", {})
    effective_db = db_path or Path(app_config.get("database", "data/academicos.db"))
    report = StagedSyncReport()
    conn = _open_db(effective_db)

    try:
        brightspace = config.get("brightspace")
        if isinstance(brightspace, dict) and brightspace.get("enabled", True):
            try:
                token = _brightspace_token(brightspace, interactive=False)
                client = BrightspaceClient(
                    host=str(brightspace["host"]),
                    bearer_token=token,
                    le_version=str(brightspace.get("le_version", "1.75")),
                    lp_version=str(brightspace.get("lp_version", "1.51")),
                )
                _merge(report, stage_brightspace(conn, client, brightspace=brightspace))
            except Exception as exc:
                report.errors["brightspace"] = f"{type(exc).__name__}: {exc}"

        mail = config.get("mail")
        if isinstance(mail, dict) and mail.get("enabled", False):
            try:
                token = acquire_graph_token(
                    client_id=str(mail["client_id"]),
                    cache_path=Path(mail.get("cache", ".auth/mail/msal_cache.json")),
                    allow_interactive=interactive_mail_auth,
                )
                mail_client = GraphMailClient(access_token=token)
                identity = persist_dataset(
                    conn,
                    dataset="m365_me",
                    payload=mail_client.me(),
                    course_id=None,
                    org_unit_id=None,
                )
                report.changed += identity["changed"]
                report.unchanged += identity["unchanged"]
                # Verify Mail.Read using metadata only. Message subject/body/recipients are neither
                # requested nor persisted and no delta cursor is created or advanced here.
                messages = mail_client.inbox_probe(top=1)
                report.mail_probe_items = len(messages)
            except Exception as exc:
                report.errors["mail:m365"] = f"{type(exc).__name__}: {exc}"

        return report
    finally:
        conn.close()
