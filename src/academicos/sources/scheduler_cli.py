from __future__ import annotations

from pathlib import Path

import typer

from academicos.sources.windows_scheduler import (
    SchedulerError,
    install_command,
    remove_command,
    run,
    status_command,
)

app = typer.Typer(help="Manage AcademicOS recurring source synchronization on Windows.")


@app.command()
def install(
    config: Path = typer.Option(Path("config.local.toml"), "--config"),
    minutes: int = typer.Option(30, "--minutes", min=15),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    if not config.exists():
        raise typer.BadParameter(f"config file not found: {config}")
    command = install_command(config, interval_minutes=minutes)
    if dry_run:
        typer.echo(command.display())
        return
    try:
        result = run(command)
    except SchedulerError as exc:
        raise typer.Exit(code=1) from exc
    typer.echo((result.stdout or "AcademicOS scheduled sync installed.").strip())


@app.command()
def status() -> None:
    try:
        result = run(status_command())
    except SchedulerError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(result.stdout.strip())


@app.command()
def remove() -> None:
    try:
        result = run(remove_command())
    except SchedulerError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo((result.stdout or "AcademicOS scheduled sync removed.").strip())


if __name__ == "__main__":
    app()
