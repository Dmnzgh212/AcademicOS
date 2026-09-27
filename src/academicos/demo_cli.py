from __future__ import annotations

from pathlib import Path

import typer

from academicos.demo import seed_demo
from academicos.storage.db import connect_db, initialize_db
from academicos.web.app import serve_dashboard

app = typer.Typer(help="Create and optionally serve a privacy-safe synthetic AcademicOS demo.")


@app.callback(invoke_without_command=True)
def main(
    db: Path = typer.Option(Path("data/demo-academicos.db"), "--db"),
    reset: bool = typer.Option(False, "--reset"),
    serve: bool = typer.Option(False, "--serve"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port", min=1, max=65535),
) -> None:
    """Seed synthetic data. Refuses non-demo-looking database names by default."""
    if "demo" not in db.name.lower():
        raise typer.BadParameter("demo DB filename must contain 'demo' to avoid touching real data")

    conn = connect_db(db)
    try:
        initialize_db(conn)
        counts = seed_demo(conn, reset=reset)
    finally:
        conn.close()

    typer.echo(
        "Demo ready · "
        f"courses={counts['courses']} sessions={counts['sessions']} tasks={counts['tasks']} "
        f"plan_blocks={counts['plan_blocks']} changes={counts['changes']} "
        f"activities={counts['activities']} · db={db}"
    )
    if serve:
        typer.echo(f"Serving demo at http://{host}:{port}")
        serve_dashboard(db, host=host, port=port)


if __name__ == "__main__":
    app()
