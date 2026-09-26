from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

from academicos.sources.health import list_health
from academicos.sources.sync import load_sync_config
from academicos.storage.db import connect_db, initialize_db

app = typer.Typer(
    help="Inspect freshness and failure state of AcademicOS collectors.",
    no_args_is_help=False,
)


def _age_hours(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - parsed).total_seconds() / 3600)


def _database_path(config: Path, db: Path | None) -> Path:
    if db is not None:
        return db
    if config.exists():
        payload = load_sync_config(config)
        app_config = payload.get("app", {}) if isinstance(payload, dict) else {}
        if isinstance(app_config, dict) and app_config.get("database"):
            return Path(str(app_config["database"]))
    return Path("data/academicos.db")


@app.callback(invoke_without_command=True)
def main(
    config: Path = typer.Option(Path("config.local.toml"), "--config"),
    db: Path | None = typer.Option(None, "--db"),
    stale_hours: float = typer.Option(6.0, "--stale-hours", min=0.1),
) -> None:
    effective_db = _database_path(config, db)
    conn = connect_db(effective_db)
    initialize_db(conn)
    try:
        rows = list_health(conn)
    finally:
        conn.close()

    if not rows:
        typer.echo("No collection health records yet. Run academicos-sync first.")
        return

    unhealthy = 0
    for row in rows:
        age = _age_hours(row.last_success_at)
        stale = age is None or age > stale_hours
        state = "ERROR" if row.status != "ok" else ("STALE" if stale else "OK")
        if state != "OK":
            unhealthy += 1
        age_text = "never" if age is None else f"{age:.1f}h"
        typer.echo(
            f"{state:<5} {row.source_key:<32} "
            f"last_success={age_text:<8} failures={row.consecutive_failures:<3} "
            f"changed={row.items_changed:<4} downloaded={row.downloaded_files}"
        )
        if row.last_error:
            typer.echo(f"      {row.last_error}", err=True)

    typer.echo(f"Health summary · sources={len(rows)} attention={unhealthy}")


if __name__ == "__main__":
    app()
