from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from academicos import __version__
from academicos.sources.capabilities import capability_rows
from academicos.sources.coverage import brightspace_coverage
from academicos.sources.doctor import run_doctor
from academicos.sources.health import list_health
from academicos.sources.sync import load_sync_config
from academicos.storage.db import connect_db, initialize_db, schema_version

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_WIN_USER_RE = re.compile(r"(?i)([A-Z]:\\Users\\)[^\\\s]+")
_POSIX_HOME_RE = re.compile(r"(/home/)[^/\s]+")
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def _redact_url(match: re.Match[str]) -> str:
    raw = match.group(0).rstrip(".,;)")
    suffix = match.group(0)[len(raw) :]
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "<url>" + suffix
    host = parsed.hostname or "redacted"
    return f"{parsed.scheme}://{host}/<redacted>" + suffix


def redact_text(value: object) -> str:
    text = str(value or "")
    text = _BEARER_RE.sub("Bearer <token>", text)
    text = _JWT_RE.sub("<token>", text)
    text = _EMAIL_RE.sub("<email>", text)
    text = _WIN_USER_RE.sub(r"\1<user>", text)
    text = _POSIX_HOME_RE.sub(r"\1<user>", text)
    text = _URL_RE.sub(_redact_url, text)
    return text


def _table_count(conn, table: str) -> int:
    # Table names are internal constants only; callers never supply this value.
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _config_summary(config: dict[str, Any]) -> dict[str, Any]:
    brightspace = config.get("brightspace")
    mail = config.get("mail")
    bs = brightspace if isinstance(brightspace, dict) else {}
    ms = mail if isinstance(mail, dict) else {}
    host = str(bs.get("host") or "")
    try:
        host_name = urlsplit(host).hostname if host else None
    except ValueError:
        host_name = None
    client_id = str(ms.get("client_id") or "")
    return {
        "brightspace": {
            "enabled": bool(bs and bs.get("enabled", True)),
            "host": host_name,
            "download_files": bool(bs.get("download_files", False)),
            "explicit_course_overrides": len(bs.get("courses", []))
            if isinstance(bs.get("courses"), list)
            else 0,
        },
        "mail": {
            "enabled": bool(ms.get("enabled", False)),
            "client_id_configured": bool(client_id and "REPLACE_WITH" not in client_id),
            "use_delta": bool(ms.get("use_delta", True)),
            "download_attachments": bool(ms.get("download_attachments", False)),
        },
        "privacy": {
            "cloud_policy": str((config.get("privacy") or {}).get("cloud_policy", "unknown"))
            if isinstance(config.get("privacy"), dict)
            else "unknown",
            "background_cloud_calls": bool((config.get("privacy") or {}).get("background_cloud_calls", False))
            if isinstance(config.get("privacy"), dict)
            else False,
        },
    }


def _doctor_summary(report) -> dict[str, Any]:
    return {
        "generated_at": report.generated_at,
        "platform": redact_text(report.platform),
        "python": report.python,
        "summary": {"failures": report.failures, "warnings": report.warnings},
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "detail": redact_text(check.detail),
            }
            for check in report.checks
        ],
    }


def build_collection_audit(
    *,
    config_path: Path,
    live: bool = False,
    bootstrap_auth: bool = False,
) -> dict[str, Any]:
    """Build an allow-listed diagnostic bundle without academic source payloads."""
    doctor = run_doctor(
        config_path=config_path,
        live=live,
        bootstrap_auth=bootstrap_auth,
    )
    config = load_sync_config(config_path) if config_path.exists() else {}
    app_config = config.get("app", {}) if isinstance(config, dict) else {}
    data_dir = Path(app_config.get("data_dir", "data")) if isinstance(app_config, dict) else Path("data")
    db_path = (
        Path(app_config.get("database", data_dir / "academicos.db"))
        if isinstance(app_config, dict)
        else data_dir / "academicos.db"
    )

    conn = connect_db(db_path)
    try:
        initialize_db(conn)
        counts = {
            table: _table_count(conn, table)
            for table in (
                "courses",
                "source_items",
                "sync_state",
                "source_health",
                "file_manifest",
                "endpoint_capabilities",
                "candidate_events",
                "tasks",
            )
        }
        health = [
            {
                "source_key": row.source_key,
                "status": row.status,
                "last_attempt_at": row.last_attempt_at,
                "last_success_at": row.last_success_at,
                "consecutive_failures": row.consecutive_failures,
                "items_changed": row.items_changed,
                "items_unchanged": row.items_unchanged,
                "downloaded_files": row.downloaded_files,
                "last_error": redact_text(row.last_error) if row.last_error else None,
            }
            for row in list_health(conn)
        ]
        capabilities = []
        for row in capability_rows(conn):
            capabilities.append(
                {
                    "source_key": row["source_key"],
                    "endpoint": row["endpoint"],
                    "status": row["status"],
                    "http_status": row["http_status"],
                    "last_checked_at": row["last_checked_at"],
                    "next_probe_at": row["next_probe_at"],
                    "response_shape": row["response_shape"],
                    "last_error": redact_text(row["last_error"]) if row["last_error"] else None,
                }
            )
        coverage = [asdict(row) | {"coverage": row.coverage} for row in brightspace_coverage(conn)]
        db_version = schema_version(conn)
    finally:
        conn.close()

    return {
        "format": "academicos.collection_audit.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "academicos_version": __version__,
        "sanitized": True,
        "privacy_note": (
            "Allow-listed diagnostics only; raw source text/JSON, tokens, cookies, email addresses, "
            "grades, and downloaded academic files are excluded."
        ),
        "config": _config_summary(config if isinstance(config, dict) else {}),
        "doctor": _doctor_summary(doctor),
        "database": {"schema_version": db_version, "counts": counts},
        "source_health": health,
        "endpoint_capabilities": capabilities,
        "brightspace_coverage": coverage,
    }


def default_audit_path(config_path: Path, generated_at: datetime | None = None) -> Path:
    config = load_sync_config(config_path)
    app_config = config.get("app", {}) if isinstance(config, dict) else {}
    data_dir = Path(app_config.get("data_dir", "data")) if isinstance(app_config, dict) else Path("data")
    stamp = (generated_at or datetime.now(UTC)).strftime("%Y%m%d-%H%M%SZ")
    return data_dir / "audits" / f"collection-audit-{stamp}.json"


def write_collection_audit(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
