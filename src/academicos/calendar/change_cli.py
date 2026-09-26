from __future__ import annotations

from pathlib import Path

import typer

from academicos.calendar.events import (
    accept_candidate_event,
    reject_candidate_event,
    rollback_candidate_event,
)
from academicos.calendar.inbox import list_candidate_inbox
from academicos.calendar.models import CandidateStatus
from academicos.storage.db import connect_db, initialize_db

app = typer.Typer(
    help="Review, apply, reject, and rollback evidence-backed academic changes.",
    no_args_is_help=True,
)

DEFAULT_DB = Path("data/academicos.db")


def _open_db(path: Path):
    conn = connect_db(path)
    initialize_db(conn)
    return conn


@app.command("list")
def list_changes(
    status_name: str = typer.Option("pending", "--status"),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
) -> None:
    """List CandidateEvents by lifecycle status."""
    try:
        selected_status = CandidateStatus(status_name)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in CandidateStatus)
        raise typer.BadParameter(f"invalid candidate status: {status_name}; choose {allowed}") from exc

    conn = _open_db(db)
    try:
        items = list_candidate_inbox(conn, status=selected_status, limit=limit)
        if not items:
            typer.echo("No matching candidate changes.")
            return
        for item in items:
            course = item.course_code or "Academic"
            if item.course_section:
                course += f" {item.course_section}"
            typer.echo(
                f"{item.id}  {item.status.value}  {item.confidence:.0%}  "
                f"{course}  {item.kind.value}  {item.title}"
            )
    finally:
        conn.close()


@app.command("accept")
def accept_change(
    candidate_id: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
) -> None:
    """Apply one reviewed CandidateEvent."""
    conn = _open_db(db)
    try:
        result = accept_candidate_event(conn, candidate_id)
        typer.echo(
            f"Accepted {result.candidate_id} -> {result.action_type} "
            f"{result.action_id or ''}".rstrip()
        )
    finally:
        conn.close()


@app.command("reject")
def reject_change(
    candidate_id: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
) -> None:
    """Reject one pending CandidateEvent."""
    conn = _open_db(db)
    try:
        result = reject_candidate_event(conn, candidate_id)
        typer.echo(f"Rejected {result.candidate_id}")
    finally:
        conn.close()


@app.command("rollback")
def rollback_change(
    candidate_id: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
) -> None:
    """Rollback the currently applied action for one accepted CandidateEvent."""
    conn = _open_db(db)
    try:
        result = rollback_candidate_event(conn, candidate_id)
        detail = f"; restored due={result.restored_due_at}" if result.restored_due_at else ""
        if result.reactivated_candidate_id:
            detail += f"; reactivated={result.reactivated_candidate_id}"
        typer.echo(
            f"Rolled back {result.candidate_id} -> {result.action_type} "
            f"{result.action_id or ''}{detail}".rstrip()
        )
    finally:
        conn.close()
