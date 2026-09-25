from __future__ import annotations

import os
import sqlite3
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from academicos.sources.brightspace.auth import (
    BrightspaceAuthError,
    get_or_refresh_token,
    load_saved_token,
)
from academicos.sources.brightspace.client import BrightspaceClient
from academicos.sources.brightspace.collector import (
    collect_course_data,
    download_course_files,
    persist_dataset,
)
from academicos.sources.brightspace.discovery import discover_course_mappings
from academicos.sources.mail.auth import acquire_graph_token
from academicos.sources.mail.collector import collect_inbox
from academicos.sources.mail.graph import GraphMailClient
from academicos.sources.state import get_cursor, set_sync_state
from academicos.storage.db import connect_db, initialize_db


@dataclass
class SyncReport:
    changed: int = 0
    unchanged: int = 0
    downloaded_files: int = 0
    sources_ok: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


def load_sync_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _open_db(path: Path) -> sqlite3.Connection:
    conn = connect_db(path)
    initialize_db(conn)
    return conn


def _resolve_course_id(conn: sqlite3.Connection, code: str, section: str | None) -> str:
    if section:
        rows = conn.execute(
            "SELECT id FROM courses WHERE UPPER(code)=UPPER(?) "
            "AND UPPER(COALESCE(section,''))=UPPER(?)",
            (code, section),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id FROM courses WHERE UPPER(code)=UPPER(?)",
            (code,),
        ).fetchall()
    if len(rows) != 1:
        raise ValueError(
            f"course mapping requires exactly one local course for {code}"
            + (f" {section}" if section else "")
        )
    return rows[0]["id"]


def _brightspace_token(config: dict[str, Any], *, interactive: bool) -> str:
    host = str(config["host"])
    auth_dir = Path(config.get("auth_dir", ".auth/brightspace"))
    token_env = str(config.get("token_env", "BRIGHTSPACE_TOKEN"))
    env_token = os.environ.get(token_env)
    if env_token:
        return env_token
    saved = load_saved_token(auth_dir)
    if saved:
        return saved
    if interactive:
        raise BrightspaceAuthError(
            "no saved Brightspace token; bootstrap once with academicos-collect brightspace-login"
        )
    return get_or_refresh_token(host=host, auth_dir=auth_dir)


def _course_specs(
    conn: sqlite3.Connection,
    brightspace: dict[str, Any],
    enrollments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return configured courses, filling missing org_ids from Brightspace discovery.

    If no explicit course list is configured, all unambiguous local timetable courses
    discovered in active Brightspace enrollments are collected automatically.
    """
    configured = brightspace.get("courses", [])
    configured = configured if isinstance(configured, list) else []
    discovery = discover_course_mappings(conn, enrollments)
    by_local_id = {mapping.local_course_id: mapping for mapping in discovery.mappings}
    errors: dict[str, str] = {}

    if not configured:
        rows = conn.execute("SELECT id, code, section FROM courses").fetchall()
        specs: list[dict[str, Any]] = []
        for row in rows:
            mapping = by_local_id.get(row["id"])
            if mapping is None:
                continue
            specs.append(
                {
                    "code": row["code"],
                    "section": row["section"],
                    "org_id": mapping.org_unit_id,
                    "download_files": bool(brightspace.get("download_files", False)),
                }
            )
        for label in discovery.unmatched_local:
            errors[f"discovery:{label}"] = "no matching active Brightspace course offering"
        for label, options in discovery.ambiguous_local.items():
            errors[f"discovery:{label}"] = "ambiguous Brightspace offerings: " + "; ".join(options)
        return specs, errors

    specs = []
    for raw in configured:
        if not isinstance(raw, dict) or not raw.get("code"):
            continue
        spec = dict(raw)
        if spec.get("org_id"):
            specs.append(spec)
            continue
        try:
            local_id = _resolve_course_id(
                conn,
                str(spec["code"]),
                str(spec["section"]) if spec.get("section") else None,
            )
        except ValueError as exc:
            errors[f"discovery:{spec['code']}"] = str(exc)
            continue
        mapping = by_local_id.get(local_id)
        if mapping is None:
            errors[f"discovery:{spec['code']}"] = "no unambiguous Brightspace course mapping"
            continue
        spec["org_id"] = mapping.org_unit_id
        specs.append(spec)
    return specs, errors


def sync_all(
    *,
    config_path: Path,
    db_path: Path | None = None,
    interactive_mail_auth: bool = False,
) -> SyncReport:
    """Run all configured source collectors without invoking external AI services."""
    config = load_sync_config(config_path)
    app_config = config.get("app", {})
    effective_db = db_path or Path(app_config.get("database", "data/academicos.db"))
    data_dir = Path(app_config.get("data_dir", "data"))
    report = SyncReport()
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

                enrollments = client.my_enrollments(active_only=True)
                feed_state_key = "brightspace:activity_feed"
                feed_since = get_cursor(conn, feed_state_key)
                account_sets = {
                    "whoami": client.whoami(),
                    "enrollments": enrollments,
                    "activity_feed": client.user_feed(since=feed_since),
                }
                for name, payload in account_sets.items():
                    result = persist_dataset(
                        conn,
                        dataset=name,
                        payload=payload,
                        course_id=None,
                        org_unit_id=None,
                    )
                    report.changed += result["changed"]
                    report.unchanged += result["unchanged"]
                set_sync_state(
                    conn,
                    feed_state_key,
                    cursor=datetime.now(UTC).isoformat(),
                    metadata={"dataset": "activity_feed"},
                )

                courses, discovery_errors = _course_specs(conn, brightspace, enrollments)
                report.errors.update(discovery_errors)
                for course in courses:
                    code = str(course["code"])
                    section = str(course["section"]) if course.get("section") else None
                    org_id = str(course["org_id"])
                    source_name = f"brightspace:{code}{'-' + section if section else ''}"
                    state_key = f"brightspace:{org_id}:course"
                    try:
                        course_id = _resolve_course_id(conn, code, section)
                        since = course.get("since") or get_cursor(conn, state_key)
                        course_report = collect_course_data(
                            conn,
                            client,
                            course_id=course_id,
                            org_unit_id=org_id,
                            since=str(since) if since else None,
                            timezone_name=str(app_config.get("timezone", "America/Toronto")),
                        )
                        report.changed += course_report.changed
                        report.unchanged += course_report.unchanged
                        for endpoint, error in course_report.errors.items():
                            report.errors[f"{source_name}:{endpoint}"] = error

                        if bool(course.get("download_files", brightspace.get("download_files", False))):
                            label = code + (f"-{section}" if section else "")
                            files = download_course_files(
                                client,
                                org_unit_id=org_id,
                                out_dir=data_dir / "courses" / label,
                            )
                            report.downloaded_files += files["downloaded"]
                            if files["failed"]:
                                report.errors[f"{source_name}:files"] = (
                                    f"{files['failed']} file(s) could not be downloaded"
                                )
                        set_sync_state(
                            conn,
                            state_key,
                            cursor=datetime.now(UTC).isoformat(),
                            metadata={"code": code, "section": section, "org_id": org_id},
                        )
                        report.sources_ok.append(source_name)
                    except Exception as exc:
                        report.errors[source_name] = f"{type(exc).__name__}: {exc}"
                report.sources_ok.append("brightspace:account")
            except Exception as exc:
                report.errors["brightspace"] = f"{type(exc).__name__}: {exc}"

        mail = config.get("mail")
        if isinstance(mail, dict) and mail.get("enabled", False):
            try:
                client_id = str(mail["client_id"])
                cache = Path(mail.get("cache", ".auth/mail/msal_cache.json"))
                token = acquire_graph_token(
                    client_id=client_id,
                    cache_path=cache,
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
                mail_state_key = "mail:m365:inbox"
                mail_since = mail.get("since") or get_cursor(conn, mail_state_key)
                inbox = collect_inbox(
                    conn,
                    mail_client,
                    since=str(mail_since) if mail_since else None,
                    max_pages=int(mail.get("max_pages", 20)),
                )
                report.changed += identity["changed"] + inbox.changed
                report.unchanged += identity["unchanged"] + inbox.unchanged
                set_sync_state(
                    conn,
                    mail_state_key,
                    cursor=datetime.now(UTC).isoformat(),
                    metadata={"provider": "microsoft_graph"},
                )
                report.sources_ok.append("mail:m365")
            except Exception as exc:
                report.errors["mail:m365"] = f"{type(exc).__name__}: {exc}"

        return report
    finally:
        conn.close()
