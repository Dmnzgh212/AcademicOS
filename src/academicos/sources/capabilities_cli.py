from __future__ import annotations

import json
from pathlib import Path

import typer

from academicos.sources.capabilities import capability_rows
from academicos.storage.db import connect_db, initialize_db

app = typer.Typer(help="Show learned source endpoint compatibility without private payload data.")


@app.callback(invoke_without_command=True)
def main(
    db: Path = typer.Option(Path("data/academicos.db"), "--db"),
    json_out: Path | None = typer.Option(None, "--json-out"),
) -> None:
    conn = connect_db(db)
    try:
        initialize_db(conn)
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
