from __future__ import annotations

from pathlib import Path

import typer

from academicos.sources.coverage import brightspace_coverage
from academicos.storage.db import connect_db, initialize_db

app = typer.Typer(help="Summarize learned Brightspace endpoint coverage.")


@app.callback(invoke_without_command=True)
def main(
    db: Path = typer.Option(Path("data/academicos.db"), "--db"),
) -> None:
    conn = connect_db(db)
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
