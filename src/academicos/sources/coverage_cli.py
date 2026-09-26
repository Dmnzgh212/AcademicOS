from __future__ import annotations

from pathlib import Path

import typer

from academicos.sources.coverage import brightspace_coverage
from academicos.sources.sync import load_sync_config
from academicos.storage.db import connect_db, initialize_db

app = typer.Typer(help="Summarize learned Brightspace endpoint coverage.")


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
) -> None:
    effective_db = _database_path(config, db)
    conn = connect_db(effective_db)
    try:
        initialize_db(conn)
        rows = brightspace_coverage(conn)
    finally:
        conn.close()

    if not rows:
        typer.echo("No Brightspace coverage data yet. Run a live doctor or source sync first.")
        return

    total_supported = 0
    total_expected = 0
    for row in rows:
        total_supported += row.supported
        total_expected += row.total
        typer.echo(
            f"{row.label:<24} {row.supported:>2}/{row.total:<2} supported  "
            f"blocked={row.blocked:<2} attention={row.attention:<2} unknown={row.unknown:<2} "
            f"coverage={row.coverage:.0%}"
        )

    overall = total_supported / total_expected if total_expected else 0.0
    typer.echo(f"Coverage summary · courses={len(rows)} supported={overall:.0%}")
