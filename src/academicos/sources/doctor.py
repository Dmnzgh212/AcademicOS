from __future__ import annotations

import importlib.util
import json
import os
import platform
import sqlite3
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from academicos.sources.brightspace.auth import (
    BrightspaceAuthError,
    capture_browser_token,
    get_or_refresh_token,
    load_saved_token,
    token_info,
)
from academicos.sources.brightspace.client import BrightspaceClient
from academicos.sources.brightspace.discovery import discover_course_mappings
from academicos.sources.mail.auth import MailAuthError, acquire_graph_token
from academicos.sources.mail.graph import GraphMailClient
from academicos.sources.sync import load_sync_config
from academicos.storage.db import connect_db, initialize_db, schema_version


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    generated_at: str
    platform: str
    python: str
    checks: tuple[DoctorCheck, ...]

    @property
    def failures(self) -> int:
        return sum(check.status == "FAIL" for check in self.checks)

    @property
    def warnings(self) -> int:
        return sum(check.status == "WARN" for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "platform": self.platform,
            "python": self.python,
            "summary": {"failures": self.failures, "warnings": self.warnings},
            "checks": [asdict(check) for check in self.checks],
        }


def _check(name: str, status: str, detail: str) -> DoctorCheck:
    return DoctorCheck(name=name, status=status, detail=detail)


def _module_status(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _writeable_directory(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix="academicos-doctor-", delete=True):
            pass
        return True, str(path.resolve())
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _open_database(path: Path) -> tuple[sqlite3.Connection | None, DoctorCheck]:
    try:
        conn = connect_db(path)
        initialize_db(conn)
        version = schema_version(conn)
        courses = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        return conn, _check(
            "database",
            "PASS",
            f"schema=v{version}; imported_courses={courses}; path={path.resolve()}",
        )
    except Exception as exc:
        return None, _check("database", "FAIL", f"{type(exc).__name__}: {exc}")


def _brightspace_token_for_doctor(
    config: dict[str, Any],
    *,
    bootstrap_auth: bool,
) -> str:
    auth_dir = Path(config.get("auth_dir", ".auth/brightspace"))
    token_env = str(config.get("token_env", "BRIGHTSPACE_TOKEN"))
    env_token = os.environ.get(token_env)
    if env_token:
        return env_token
    saved = load_saved_token(auth_dir)
    if saved:
        return saved
    host = str(config["host"])
    if bootstrap_auth:
        return capture_browser_token(
            host=host,
            auth_dir=auth_dir,
            headless=False,
            channel="auto",
        )
    return get_or_refresh_token(host=host, auth_dir=auth_dir)


def _probe_brightspace(
    checks: list[DoctorCheck],
    conn: sqlite3.Connection | None,
    config: dict[str, Any],
    *,
    live: bool,
    bootstrap_auth: bool,
) -> None:
    auth_dir = Path(config.get("auth_dir", ".auth/brightspace"))
    info = token_info(auth_dir)
    playwright_ready = _module_status("playwright")
    status = str(info.get("status", "missing"))
    profile = bool(info.get("browser_profile"))
    checks.append(
        _check(
            "brightspace.auth.local",
            "PASS" if status == "valid" else "WARN",
            f"token={status}; browser_profile={profile}; playwright={playwright_ready}",
        )
    )
    if not live:
        return
    if conn is None:
        checks.append(_check("brightspace.live", "SKIP", "database unavailable"))
        return

    try:
        token = _brightspace_token_for_doctor(config, bootstrap_auth=bootstrap_auth)
        client = BrightspaceClient(
            host=str(config["host"]),
            bearer_token=token,
            le_version=str(config.get("le_version", "1.75")),
            lp_version=str(config.get("lp_version", "1.51")),
        )
        identity = client.whoami()
        enrollments = client.my_enrollments(active_only=True)
        user_id = identity.get("Identifier") or identity.get("UserId") or "available"
        checks.append(
            _check(
                "brightspace.live.account",
                "PASS",
                f"whoami={user_id}; active_enrollments={len(enrollments)}",
            )
        )
    except Exception as exc:
        checks.append(
            _check("brightspace.live.account", "FAIL", f"{type(exc).__name__}: {exc}")
        )
        return

    discovery = discover_course_mappings(conn, enrollments)
    checks.append(
        _check(
            "brightspace.course_discovery",
            "PASS" if discovery.mappings else "WARN",
            (
                f"mapped={len(discovery.mappings)}; unmatched={len(discovery.unmatched_local)}; "
                f"ambiguous={len(discovery.ambiguous_local)}"
            ),
        )
    )
    if not discovery.mappings:
        return

    sample = discovery.mappings[0]
    org_id = sample.org_unit_id
    code = sample.local_code
    probes: tuple[tuple[str, Callable[[], Any]], ...] = (
        ("news", lambda: client.news(org_id)),
        ("assignments", lambda: client.assignments(org_id)),
        ("quizzes", lambda: client.quizzes(org_id)),
        ("content_toc", lambda: client.content_toc(org_id)),
        ("grades", lambda: client.grades(org_id)),
        ("calendar", lambda: client.calendar_events(org_id)),
        ("updates", lambda: client.updates(org_id)),
    )
    for label, operation in probes:
        try:
            payload = operation()
            if isinstance(payload, (list, tuple, dict)):
                count = len(payload)
                detail = f"course={code}; response_items={count}"
            else:
                detail = f"course={code}; response_type={type(payload).__name__}"
            checks.append(_check(f"brightspace.endpoint.{label}", "PASS", detail))
        except Exception as exc:
            # Institution/course permissions can legitimately disable an endpoint.
            checks.append(
                _check(
                    f"brightspace.endpoint.{label}",
                    "WARN",
                    f"course={code}; {type(exc).__name__}: {exc}",
                )
            )


def _probe_mail(
    checks: list[DoctorCheck],
    config: dict[str, Any],
    *,
    live: bool,
    bootstrap_auth: bool,
) -> None:
    client_id = str(config.get("client_id") or "").strip()
    cache = Path(config.get("cache", ".auth/mail/msal_cache.json"))
    msal_ready = _module_status("msal")
    configured = bool(client_id and "REPLACE_WITH" not in client_id)
    checks.append(
        _check(
            "mail.auth.local",
            "PASS" if configured and msal_ready else "WARN",
            f"client_id_configured={configured}; msal={msal_ready}; token_cache={cache.exists()}",
        )
    )
    if not live:
        return
    if not configured:
        checks.append(_check("mail.live", "SKIP", "mail.client_id is not configured"))
        return
    try:
        token = acquire_graph_token(
            client_id=client_id,
            cache_path=cache,
            allow_interactive=bootstrap_auth,
            prompt=print if bootstrap_auth else None,
        )
        client = GraphMailClient(access_token=token)
        identity = client.me()
        messages = client.inbox_messages(top=1, max_pages=1)
        account = identity.get("userPrincipalName") or identity.get("mail") or "available"
        checks.append(
            _check(
                "mail.live",
                "PASS",
                f"account={account}; inbox_probe_items={len(messages)}",
            )
        )
    except (MailAuthError, Exception) as exc:
        checks.append(_check("mail.live", "FAIL", f"{type(exc).__name__}: {exc}"))


def run_doctor(
    *,
    config_path: Path,
    live: bool = False,
    bootstrap_auth: bool = False,
) -> DoctorReport:
    checks: list[DoctorCheck] = []
    checks.append(
        _check(
            "python",
            "PASS" if sys.version_info >= (3, 11) else "FAIL",
            platform.python_version(),
        )
    )
    checks.append(_check("platform", "PASS", platform.platform()))

    if not config_path.exists():
        checks.append(_check("config", "FAIL", f"not found: {config_path}"))
        return DoctorReport(
            generated_at=datetime.now(UTC).isoformat(),
            platform=platform.platform(),
            python=platform.python_version(),
            checks=tuple(checks),
        )

    try:
        config = load_sync_config(config_path)
        checks.append(_check("config", "PASS", str(config_path.resolve())))
    except Exception as exc:
        checks.append(_check("config", "FAIL", f"{type(exc).__name__}: {exc}"))
        return DoctorReport(
            generated_at=datetime.now(UTC).isoformat(),
            platform=platform.platform(),
            python=platform.python_version(),
            checks=tuple(checks),
        )

    app_config = config.get("app", {})
    data_dir = Path(app_config.get("data_dir", "data"))
    writable, detail = _writeable_directory(data_dir)
    checks.append(_check("data_dir", "PASS" if writable else "FAIL", detail))

    db_path = Path(app_config.get("database", data_dir / "academicos.db"))
    conn, db_check = _open_database(db_path)
    checks.append(db_check)

    try:
        brightspace = config.get("brightspace")
        if isinstance(brightspace, dict) and brightspace.get("enabled", True):
            _probe_brightspace(
                checks,
                conn,
                brightspace,
                live=live,
                bootstrap_auth=bootstrap_auth,
            )
        else:
            checks.append(_check("brightspace", "SKIP", "disabled"))

        mail = config.get("mail")
        if isinstance(mail, dict) and mail.get("enabled", False):
            _probe_mail(checks, mail, live=live, bootstrap_auth=bootstrap_auth)
        else:
            checks.append(_check("mail", "SKIP", "disabled"))
    finally:
        if conn is not None:
            conn.close()

    return DoctorReport(
        generated_at=datetime.now(UTC).isoformat(),
        platform=platform.platform(),
        python=platform.python_version(),
        checks=tuple(checks),
    )


def write_doctor_report(report: DoctorReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path
