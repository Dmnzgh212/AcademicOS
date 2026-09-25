from __future__ import annotations

from pathlib import Path

import typer

from academicos.sources.lock import SyncAlreadyRunning, sync_lock
from academicos.sources.run_ledger import run_tracked_sync
from academicos.sources.sync import load_sync_config

app = typer.Typer(
    help="Run configured AcademicOS read-only source synchronization.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(
    config: Path = typer.Option(Path("config.local.toml"), "--config"),
    db: Path | None = typer.Option(None, "--db"),
    interactive_mail_auth: bool = typer.Option(False, "--interactive-mail-auth"),
) -> None:
    """Sync Brightspace and Microsoft 365 sources from one local config file."""
    if not config.exists():
        raise typer.BadParameter(f"config file not found: {config}")

    loaded = load_sync_config(config)
    app_config = loaded.get("app", {})
    effective_db = db or Path(app_config.get("database", "data/academicos.db"))
    lock_path = effective_db.with_suffix(effective_db.suffix + ".sync.lock")

    try:
        with sync_lock(lock_path):
            report, ledger = run_tracked_sync(
                config_path=config,
                db_path=db,
                interactive_mail_auth=interactive_mail_auth,
            )
    except SyncAlreadyRunning as exc:
        typer.echo(f"Sync skipped: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(
        f"Sync complete · status={ledger.status.upper()} "
        f"changed={report.changed} unchanged={report.unchanged} "
        f"downloaded_files={report.downloaded_files} errors={len(report.errors)}"
    )
    typer.echo(
        f"Run ledger · sources={ledger.source_count} ok={ledger.ok_count} "
        f"partial={ledger.partial_count} failed={ledger.failed_count}"
    )
    for source in report.sources_ok:
        typer.echo(f"  OK   {source}")
    for source, error in report.errors.items():
        typer.echo(f"  WARN {source}: {error}", err=True)


if __name__ == "__main__":
    app()
