from __future__ import annotations

import os
from pathlib import Path

import typer

from academicos.sources.brightspace.auth import (
    BrightspaceAuthError,
    capture_browser_token,
    get_or_refresh_token,
    load_saved_token,
    token_info,
)
from academicos.sources.brightspace.client import BrightspaceClient
from academicos.sources.brightspace.collector import (
    collect_course_data,
    download_course_files,
    persist_dataset,
)
from academicos.sources.mail.auth import MailAuthError, acquire_graph_token
from academicos.sources.mail.collector import collect_inbox
from academicos.sources.mail.graph import GraphMailClient
from academicos.storage.db import connect_db, initialize_db

app = typer.Typer(
    help="AcademicOS read-only source acquisition tools.",
    no_args_is_help=True,
)

DEFAULT_DB = Path("data/academicos.db")
DEFAULT_AUTH_DIR = Path(".auth/brightspace")
DEFAULT_MAIL_CACHE = Path(".auth/mail/msal_cache.json")


def _open_db(path: Path):
    conn = connect_db(path)
    initialize_db(conn)
    return conn


def _resolve_course_id(conn, code: str, section: str | None) -> str:
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
    if not rows:
        raise typer.BadParameter(f"course not found: {code}")
    if len(rows) > 1:
        raise typer.BadParameter(f"multiple {code} sections exist; pass --section")
    return rows[0]["id"]


def _token(host: str, auth_dir: Path, token_env: str, refresh: bool) -> str:
    env_token = os.environ.get(token_env)
    if env_token:
        return env_token
    saved = load_saved_token(auth_dir)
    if saved:
        return saved
    if not refresh:
        raise typer.BadParameter(
            f"no valid token in {token_env} or {auth_dir / 'token.json'}; run brightspace-login"
        )
    try:
        return get_or_refresh_token(host=host, auth_dir=auth_dir)
    except BrightspaceAuthError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _client(host: str, token: str, le_version: str, lp_version: str) -> BrightspaceClient:
    return BrightspaceClient(
        host=host,
        bearer_token=token,
        le_version=le_version,
        lp_version=lp_version,
    )


@app.command("brightspace-login")
def brightspace_login(
    host: str = typer.Option(..., "--host"),
    auth_dir: Path = typer.Option(DEFAULT_AUTH_DIR, "--auth-dir"),
    channel: str = typer.Option("auto", "--channel"),
) -> None:
    """Open a persistent browser for normal SSO/MFA and save only the D2L token locally."""
    try:
        capture_browser_token(
            host=host,
            auth_dir=auth_dir,
            headless=False,
            channel=channel,
        )
    except BrightspaceAuthError as exc:
        raise typer.BadParameter(str(exc)) from exc
    info = token_info(auth_dir)
    typer.echo(
        f"Brightspace token saved locally · status={info['status']} · "
        f"remaining={info.get('remaining_seconds', 0) // 60} min"
    )


@app.command("brightspace-token")
def brightspace_token(
    auth_dir: Path = typer.Option(DEFAULT_AUTH_DIR, "--auth-dir"),
) -> None:
    """Show local token metadata without printing the token itself."""
    info = token_info(auth_dir)
    typer.echo(
        f"status={info['status']} · browser_profile={info.get('browser_profile', False)} · "
        f"remaining={info.get('remaining_seconds', 0) // 60} min"
    )


@app.command("brightspace-account")
def brightspace_account(
    host: str = typer.Option(..., "--host"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    auth_dir: Path = typer.Option(DEFAULT_AUTH_DIR, "--auth-dir"),
    token_env: str = typer.Option("BRIGHTSPACE_TOKEN", "--token-env"),
    le_version: str = typer.Option("1.75", "--le-version"),
    lp_version: str = typer.Option("1.51", "--lp-version"),
    refresh: bool = typer.Option(True, "--refresh/--no-refresh"),
    since: str | None = typer.Option(None, "--since"),
) -> None:
    """Collect account-level identity, enrollments, and Brightspace activity feed."""
    token = _token(host, auth_dir, token_env, refresh)
    client = _client(host, token, le_version, lp_version)
    conn = _open_db(db)
    try:
        datasets = {
            "whoami": client.whoami(),
            "enrollments": client.my_enrollments(active_only=True),
            "activity_feed": client.user_feed(since=since),
        }
        total_changed = 0
        for name, payload in datasets.items():
            result = persist_dataset(
                conn,
                dataset=name,
                payload=payload,
                course_id=None,
                org_unit_id=None,
            )
            total_changed += result["changed"]
            typer.echo(
                f"{name}: fetched={result['fetched']} changed={result['changed']} "
                f"unchanged={result['unchanged']}"
            )
        typer.echo(f"Account collection complete · changed={total_changed}")
    finally:
        conn.close()


@app.command("brightspace-course")
def brightspace_course(
    course_code: str = typer.Option(..., "--course"),
    org_id: str = typer.Option(..., "--org-id"),
    host: str = typer.Option(..., "--host"),
    section: str | None = typer.Option(None, "--section"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    auth_dir: Path = typer.Option(DEFAULT_AUTH_DIR, "--auth-dir"),
    token_env: str = typer.Option("BRIGHTSPACE_TOKEN", "--token-env"),
    le_version: str = typer.Option("1.75", "--le-version"),
    lp_version: str = typer.Option("1.51", "--lp-version"),
    refresh: bool = typer.Option(True, "--refresh/--no-refresh"),
    since: str | None = typer.Option(None, "--since"),
    start: str | None = typer.Option(None, "--start"),
    end: str | None = typer.Option(None, "--end"),
    files: bool = typer.Option(False, "--files"),
    data_dir: Path = typer.Option(Path("data/courses"), "--data-dir"),
    timezone_name: str = typer.Option("America/Toronto", "--timezone"),
) -> None:
    """Mirror the main read-only Brightspace datasets for one course into local storage."""
    token = _token(host, auth_dir, token_env, refresh)
    client = _client(host, token, le_version, lp_version)
    conn = _open_db(db)
    try:
        course_id = _resolve_course_id(conn, course_code, section)
        report = collect_course_data(
            conn,
            client,
            course_id=course_id,
            org_unit_id=org_id,
            since=since,
            start=start,
            end=end,
            timezone_name=timezone_name,
        )
        for name, result in report.datasets.items():
            typer.echo(
                f"{name}: fetched={result['fetched']} changed={result['changed']} "
                f"unchanged={result['unchanged']}"
            )
        for name, error in report.errors.items():
            typer.echo(f"{name}: skipped/error · {error}", err=True)

        if files:
            label = course_code + (f"-{section}" if section else "")
            file_result = download_course_files(
                client,
                org_unit_id=org_id,
                out_dir=data_dir / label,
            )
            typer.echo(
                f"files: downloaded={file_result['downloaded']} "
                f"unchanged={file_result['unchanged']} failed={file_result['failed']}"
            )

        typer.echo(
            f"Course collection complete · changed={report.changed} · "
            f"unchanged={report.unchanged} · endpoint_errors={len(report.errors)}"
        )
    finally:
        conn.close()


@app.command("mail-inbox")
def mail_inbox(
    client_id: str = typer.Option(..., "--client-id", help="Azure public-client application ID."),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    cache: Path = typer.Option(DEFAULT_MAIL_CACHE, "--cache"),
    since: str | None = typer.Option(None, "--since"),
    max_pages: int = typer.Option(20, "--max-pages", min=1, max=200),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive"),
) -> None:
    """Read the Microsoft 365 Inbox with delegated User.Read + Mail.Read permissions."""
    try:
        token = acquire_graph_token(
            client_id=client_id,
            cache_path=cache,
            allow_interactive=interactive,
            prompt=typer.echo,
        )
    except MailAuthError as exc:
        raise typer.BadParameter(str(exc)) from exc

    client = GraphMailClient(access_token=token)
    conn = _open_db(db)
    try:
        identity = persist_dataset(
            conn,
            dataset="m365_me",
            payload=client.me(),
            course_id=None,
            org_unit_id=None,
        )
        report = collect_inbox(
            conn,
            client,
            since=since,
            max_pages=max_pages,
        )
        typer.echo(
            f"mail identity: changed={identity['changed']} unchanged={identity['unchanged']}"
        )
        typer.echo(
            f"mail inbox: fetched={report.fetched} changed={report.changed} "
            f"unchanged={report.unchanged} attachment_metadata={report.attachment_metadata}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    app()
