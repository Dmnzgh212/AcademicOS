from __future__ import annotations

import json
from pathlib import Path

import typer

from academicos.sources.capabilities import capability_rows
from academicos.sources.sync import load_sync_config
from academicos.storage.db import connect_db, initialize_db

app = typer.Typer(help="Show or reset learned source endpoint compatibility without private payload data.")


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
    json_out: Path | None = typer.Option(None, "--json-out"),
    reset_endpoint: str | None = typer.Option(
        None,
        "--reset-endpoint",
        help="Forget cached compatibility for this endpoint so the next run probes it again.",
    ),
) -> None:
    effective_db = _database_path(config, db)
    conn = connect_db(effective_db)
    try:
        initialize_db(conn)
        if reset_endpoint:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM endpoint_capabilities WHERE endpoint = ?",
                    (reset_endpoint,),
                )
            typer.echo(
                f"Reset endpoint capability cache · endpoint={reset_endpoint} rows={cursor.rowcount}"
            )
        rows = capability_rows(conn)
    finally:
        conn.close()

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        typer.echo(f"Wrote sanitized capability report: {json_out}")

    if not rows:
        typer.echo("No endpoint capabilities recorded yet. Run a live doctor or source sync first.")
        return

    for row in rows:
        http = row["http_status"] if row["http_status"] is not None else "-"
        retry = row["next_probe_at"] or "-"
        typer.echo(
            f"{row['status'].upper():11} {row['source_key']} {row['endpoint']} "
            f"http={http} next_probe={retry}"
        )
