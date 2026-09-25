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
from academicos.sources.brightspace.collector import collect_course_data, persist_dataset
from academicos.sources.brightspace.discovery import discover_course_mappings
from academicos.sources.brightspace.downloads import download_course_files_manifested
from academicos.sources.health import mark_failure, mark_success
from academicos.sources.mail.auth import acquire_graph_token
from academicos.sources.mail.collector import collect_inbox
from academicos.sources.mail.delta import collect_inbox_delta
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


def _sync_brightspace(
    conn: sqlite3.Connection,
    report: SyncReport,
    *,
    brightspace: dict[str, Any],
    app_config: dict[str, Any],
    data_dir: Path,
) -> None:
    account_health = "brightspace:account"
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
        account_changed = 0
        account_unchanged = 0
        for name, payload in account_sets.items():
            result = persist_dataset(
                conn,
                dataset=name,
                payload=payload,
                course_id=None,
                org_unit_id=None,
            )
            account_changed += result["changed"]
            account_unchanged += result["unchanged"]
            report.changed += result["changed"]
            report.unchanged += result["unchanged"]
        set_sync_state(
            conn,
            feed_state_key,
            cursor=datetime.now(UTC).isoformat(),
            metadata={"dataset": "activity_feed"},
        )
        mark_success(
            conn,
            account_health,
            changed=account_changed,
            unchanged=account_unchanged,
            metadata={"active_enrollments": len(enrollments)},
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

                downloaded = 0
                if bool(course.get("download_files", brightspace.get("download_files", False))):
                    label = code + (f"-{section}" if section else "")
                    files = download_course_files_manifested(
                        conn,
                        client,
                        org_unit_id=org_id,
                        out_dir=data_dir / "courses" / label,
                    )
                    downloaded = files["downloaded"]
                    report.downloaded_files += downloaded
                    if files["failed"]:
                        report.errors[f"{source_name}:files"] = (
                            f"{files['failed']} file(s) could not be downloaded"
                        )

                if course_report.errors:
                    error_text = "; ".join(
                        f"{key}={value}" for key, value in sorted(course_report.errors.items())
                    )
                    mark_failure(
                        conn,
                        source_name,
                        error_text,
                        metadata={"org_id": org_id, "partial": True},
                    )
                else:
                    mark_success(
                        conn,
                        source_name,
                        changed=course_report.changed,
                        unchanged=course_report.unchanged,
                        downloaded_files=downloaded,
                        metadata={"org_id": org_id, "section": section},
                    )

                set_sync_state(
                    conn,
                    state_key,
                    cursor=datetime.now(UTC).isoformat(),
                    metadata={"code": code, "section": section, "org_id": org_id},
                )
                report.sources_ok.append(source_name)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                report.errors[source_name] = error
                mark_failure(conn, source_name, error, metadata={"org_id": org_id})
        report.sources_ok.append(account_health)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        report.errors["brightspace"] = error
        mark_failure(conn, account_health, error)


def _sync_mail(
    conn: sqlite3.Connection,
    report: SyncReport,
    *,
    mail: dict[str, Any],
    interactive_mail_auth: bool,
) -> None:
    health_key = "mail:m365"
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
        state_key = "mail:m365:inbox"
        cursor = get_cursor(conn, state_key)
        use_delta = bool(mail.get("use_delta", True))

        if use_delta:
            delta_cursor = cursor if cursor and cursor.startswith("https://") else None
            inbox = collect_inbox_delta(
                conn,
                mail_client,
                delta_link=delta_cursor,
                max_pages=int(mail.get("max_pages", 50)),
            )
            if not inbox.complete or not inbox.delta_link:
                raise RuntimeError(
                    "Microsoft Graph delta sync did not reach a durable deltaLink; "
                    "increase mail.max_pages before advancing the cursor"
                )
            set_sync_state(
                conn,
                state_key,
                cursor=inbox.delta_link,
                metadata={
                    "provider": "microsoft_graph",
                    "mode": "delta",
                    "removed": inbox.removed,
                },
            )
            mail_changed = inbox.changed
            mail_unchanged = inbox.unchanged
            metadata = {"mode": "delta", "removed": inbox.removed}
        else:
            since = mail.get("since") or cursor
            inbox = collect_inbox(
                conn,
                mail_client,
                since=str(since) if since else None,
                max_pages=int(mail.get("max_pages", 20)),
            )
            set_sync_state(
                conn,
                state_key,
                cursor=datetime.now(UTC).isoformat(),
                metadata={"provider": "microsoft_graph", "mode": "timestamp"},
            )
            mail_changed = inbox.changed
            mail_unchanged = inbox.unchanged
            metadata = {"mode": "timestamp"}

        report.changed += identity["changed"] + mail_changed
        report.unchanged += identity["unchanged"] + mail_unchanged
        mark_success(
            conn,
            health_key,
            changed=identity["changed"] + mail_changed,
            unchanged=identity["unchanged"] + mail_unchanged,
            metadata=metadata,
        )
        report.sources_ok.append(health_key)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        report.errors[health_key] = error
        mark_failure(conn, health_key, error)


def sync_all(
    *,
    config_path: Path,
    db_path: Path | None = None,
    interactive_mail_auth: bool = False,
) -> SyncReport:
    """Run configured read-only collectors without invoking external AI services."""
    config = load_sync_config(config_path)
    app_config = config.get("app", {})
    effective_db = db_path or Path(app_config.get("database", "data/academicos.db"))
    data_dir = Path(app_config.get("data_dir", "data"))
    report = SyncReport()
    conn = _open_db(effective_db)

    try:
        brightspace = config.get("brightspace")
        if isinstance(brightspace, dict) and brightspace.get("enabled", True):
            _sync_brightspace(
                conn,
                report,
                brightspace=brightspace,
                app_config=app_config,
                data_dir=data_dir,
            )

        mail = config.get("mail")
        if isinstance(mail, dict) and mail.get("enabled", False):
            _sync_mail(
                conn,
                report,
                mail=mail,
                interactive_mail_auth=interactive_mail_auth,
            )

        return report
    finally:
        conn.close()
