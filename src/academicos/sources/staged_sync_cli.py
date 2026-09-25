from __future__ import annotations

from pathlib import Path

import typer

from academicos.sources.lock import SyncAlreadyRunning, sync_lock
from academicos.sources.staged_sync import run_staged_sync
from academicos.sources.sync import load_sync_config

app = typer.Typer(
    help="Run a bounded first live sync without advancing cursors or downloading files.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(
    config: Path = typer.Option(Path("config.local.toml"), "--config"),
    db: Path | None = typer.Option(None, "--db"),
    interactive_mail_auth: bool = typer.Option(False, "--interactive-mail-auth"),
) -> None:
    if not config.exists():
        raise typer.BadParameter(f"config file not found: {config}")

    loaded = load_sync_config(config)
    app_config = loaded.get("app", {})
    effective_db = db or Path(app_config.get("database", "data/academicos.db"))
    lock_path = effective_db.with_suffix(effective_db.suffix + ".sync.lock")

    try:
        with sync_lock(lock_path):
            report = run_staged_sync(
                config_path=config,
                db_path=db,
                interactive_mail_auth=interactive_mail_auth,
            )
    except SyncAlreadyRunning as exc:
        typer.echo(f"Staged sync skipped: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(
        "Staged sync complete · "
        f"courses={report.courses_checked} endpoints_checked={report.endpoints_checked} "
        f"endpoints_skipped={report.endpoints_skipped} changed={report.changed} "
        f"unchanged={report.unchanged} mail_probe_items={report.mail_probe_items} "
        f"errors={len(report.errors)}"
    )
    typer.echo("Safety · cursors_advanced=0 downloaded_files=0")
    for source, error in report.errors.items():
        typer.echo(f"  WARN {source}: {error}", err=True)


if __name__ == "__main__":
    app()
