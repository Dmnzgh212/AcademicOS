from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import typer

from academicos.calendar.timetable import import_timetable, load_timetable
from academicos.calendar.truth import effective_sessions_for_date, effective_sessions_for_range
from academicos.sources.brightspace.announcements import (
    ingest_announcements,
    load_announcement_json,
    sync_announcements,
)
from academicos.sources.brightspace.client import BrightspaceClient
from academicos.storage.db import connect_db, initialize_db, schema_version

app = typer.Typer(
    help="AcademicOS local academic planning system.",
    no_args_is_help=True,
)

DEFAULT_DB = Path("data/academicos.db")


def _open_db(path: Path):
    conn = connect_db(path)
    initialize_db(conn)
    return conn


def _resolve_course_id(conn, code: str, section: str | None) -> str:  # noqa: ANN001
    if section:
        rows = conn.execute(
            "SELECT id FROM courses WHERE UPPER(code) = UPPER(?) AND UPPER(COALESCE(section, '')) = UPPER(?)",
            (code, section),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id FROM courses WHERE UPPER(code) = UPPER(?)",
            (code,),
        ).fetchall()
    if not rows:
        raise typer.BadParameter(f"course not found: {code}{' ' + section if section else ''}")
    if len(rows) > 1:
        raise typer.BadParameter(
            f"multiple {code} sections exist; pass --section to select one"
        )
    return rows[0]["id"]


@app.command("status")
def status(db: Path = typer.Option(DEFAULT_DB, "--db")) -> None:
    """Show local database and Calendar v0.1 status."""
    conn = _open_db(db)
    try:
        counts = {}
        for table in (
            "courses",
            "course_sessions",
            "source_items",
            "candidate_events",
            "event_overrides",
            "tasks",
            "plan_blocks",
        ):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        typer.echo(
            f"AcademicOS schema v{schema_version(conn)} | "
            f"courses={counts['courses']} | "
            f"sessions={counts['course_sessions']} | "
            f"sources={counts['source_items']} | "
            f"candidates={counts['candidate_events']} | "
            f"overrides={counts['event_overrides']} | "
            f"tasks={counts['tasks']} | "
            f"plan_blocks={counts['plan_blocks']}"
        )
    finally:
        conn.close()


@app.command("init-db")
def init_db(db: Path = typer.Option(DEFAULT_DB, "--db")) -> None:
    """Create or migrate the local AcademicOS database."""
    conn = _open_db(db)
    try:
        typer.echo(f"Initialized {db} at schema v{schema_version(conn)}")
    finally:
        conn.close()


@app.command("timetable-import")
def timetable_import(
    timetable: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
) -> None:
    """Import an authoritative semester timetable JSON file."""
    document = load_timetable(timetable)
    conn = _open_db(db)
    try:
        result = import_timetable(conn, document)
        typer.echo(
            f"Imported {result['courses']} course(s), "
            f"{result['sessions']} recurring session(s) "
            f"for {document.term}."
        )
    finally:
        conn.close()


@app.command("announcements-import")
def announcements_import(
    source: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    course_code: str = typer.Option(..., "--course"),
    org_id: str = typer.Option(..., "--org-id"),
    section: str | None = typer.Option(None, "--section"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    timezone_name: str = typer.Option("America/Toronto", "--timezone"),
    auto_accept: bool = typer.Option(False, "--auto-accept"),
) -> None:
    """Ingest a saved Brightspace announcement JSON payload."""
    raw = load_announcement_json(source)
    conn = _open_db(db)
    try:
        course_id = _resolve_course_id(conn, course_code, section)
        result = ingest_announcements(
            conn,
            raw,
            course_id=course_id,
            org_unit_id=org_id,
            timezone_name=timezone_name,
            auto_accept=auto_accept,
        )
        typer.echo(
            "Announcements: "
            f"fetched={result['fetched']} changed={result['changed']} "
            f"unchanged={result['unchanged']} candidates={result['candidates']} "
            f"auto_accepted={result['auto_accepted']} auto_skipped={result['auto_skipped']}"
        )
    finally:
        conn.close()


@app.command("brightspace-news-sync")
def brightspace_news_sync(
    course_code: str = typer.Option(..., "--course"),
    org_id: str = typer.Option(..., "--org-id"),
    host: str = typer.Option(..., "--host", help="Brightspace host, e.g. https://uottawa.brightspace.com"),
    section: str | None = typer.Option(None, "--section"),
    since: str | None = typer.Option(None, "--since", help="ISO timestamp passed to Brightspace news endpoint."),
    le_version: str = typer.Option("1.75", "--le-version"),
    token_env: str = typer.Option("BRIGHTSPACE_TOKEN", "--token-env"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    timezone_name: str = typer.Option("America/Toronto", "--timezone"),
    auto_accept: bool = typer.Option(False, "--auto-accept"),
) -> None:
    """Fetch course announcements from Brightspace and ingest them locally."""
    token = os.environ.get(token_env)
    if not token:
        raise typer.BadParameter(
            f"environment variable {token_env} is empty; tokens are intentionally not accepted on the command line"
        )

    conn = _open_db(db)
    try:
        course_id = _resolve_course_id(conn, course_code, section)
        client = BrightspaceClient(
            host=host,
            bearer_token=token,
            le_version=le_version,
        )
        result = sync_announcements(
            conn,
            client,
            course_id=course_id,
            org_unit_id=org_id,
            since=since,
            timezone_name=timezone_name,
            auto_accept=auto_accept,
        )
        typer.echo(
            "Brightspace news sync: "
            f"fetched={result['fetched']} changed={result['changed']} "
            f"unchanged={result['unchanged']} candidates={result['candidates']} "
            f"auto_accepted={result['auto_accepted']} auto_skipped={result['auto_skipped']}"
        )
    finally:
        conn.close()


@app.command("day")
def day(
    target: str = typer.Argument(..., help="Date in YYYY-MM-DD format."),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    timezone_name: str = typer.Option("America/Toronto", "--timezone"),
    include_cancelled: bool = typer.Option(False, "--include-cancelled"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Render the effective Truth Calendar for one day."""
    target_date = date.fromisoformat(target)
    conn = _open_db(db)
    try:
        sessions = effective_sessions_for_date(
            conn,
            target_date,
            timezone_name=timezone_name,
            include_cancelled=include_cancelled,
        )

        if json_output:
            typer.echo(
                json.dumps(
                    [item.model_dump(mode="json") for item in sessions],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        typer.echo(f"{target_date.isoformat()} · Truth Calendar")
        if not sessions:
            typer.echo("No scheduled academic sessions.")
            return

        for item in sessions:
            section = f" {item.course_section}" if item.course_section else ""
            location = f" · {item.location}" if item.location else ""
            mode = f" · {item.delivery_mode}" if item.delivery_mode else ""
            status = "" if item.status.value == "scheduled" else f" · {item.status.value.upper()}"
            typer.echo(
                f"{item.start_at:%H:%M}–{item.end_at:%H:%M}  "
                f"{item.course_code}{section}  "
                f"{item.session_type.value}{location}{mode}{status}"
            )
    finally:
        conn.close()


@app.command("week")
def week(
    target: str = typer.Argument(..., help="Any date inside the desired week (YYYY-MM-DD)."),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    timezone_name: str = typer.Option("America/Toronto", "--timezone"),
) -> None:
    """Render Monday-Sunday effective Truth Calendar."""
    chosen = date.fromisoformat(target)
    monday = chosen - timedelta(days=chosen.weekday())
    sunday = monday + timedelta(days=6)

    conn = _open_db(db)
    try:
        days = effective_sessions_for_range(
            conn,
            monday,
            sunday,
            timezone_name=timezone_name,
        )
        typer.echo(f"Week {monday.isoformat()} → {sunday.isoformat()}")
        for day_date, sessions in days.items():
            typer.echo(f"\n{day_date:%A · %Y-%m-%d}")
            if not sessions:
                typer.echo("  —")
                continue
            for item in sessions:
                section = f" {item.course_section}" if item.course_section else ""
                location = f" · {item.location}" if item.location else ""
                typer.echo(
                    f"  {item.start_at:%H:%M}–{item.end_at:%H:%M}  "
                    f"{item.course_code}{section}  {item.session_type.value}{location}"
                )
    finally:
        conn.close()


@app.command("sync")
def sync() -> None:
    """Placeholder for orchestrated Brightspace/email synchronization."""
    typer.echo("Full source sync orchestration is not implemented yet.")


if __name__ == "__main__":
    app()
