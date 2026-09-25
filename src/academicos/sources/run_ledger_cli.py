from __future__ import annotations

from pathlib import Path

import typer

from academicos.sources.run_ledger import list_sync_runs, sync_run_sources
from academicos.sources.sync import load_sync_config
from academicos.storage.db import connect_db, initialize_db

app = typer.Typer(
    help="Inspect recent AcademicOS source-sync completeness without showing source content.",
    no_args_is_help=False,
)


def _database_path(config: Path, db: Path | None) -> Path:
    if db is not None:
        return db
    if config.exists():
        loaded = load_sync_config(config)
        return Path(loaded.get("app", {}).get("database", "data/academicos.db"))
    return Path("data/academicos.db")


@app.callback(invoke_without_command=True)
def main(
    config: Path = typer.Option(Path("config.local.toml"), "--config"),
    db: Path | None = typer.Option(None, "--db"),
    limit: int = typer.Option(10, "--limit", min=1, max=100),
    sources: bool = typer.Option(False, "--sources", help="Show source-level rows per run."),
) -> None:
    """Show newest sync runs first."""
    database = _database_path(config, db)
    conn = connect_db(database)
    initialize_db(conn)
    try:
        runs = list_sync_runs(conn, limit=limit)
        if not runs:
            typer.echo("No tracked sync runs yet.")
            return

        for run in runs:
            typer.echo(
                f"{str(run['status']).upper():8} {run['finished_at']} "
                f"sources={run['source_count']} ok={run['ok_count']} "
                f"partial={run['partial_count']} failed={run['failed_count']} "
                f"changed={run['items_changed']} files={run['downloaded_files']}"
            )
            if sources:
                for item in sync_run_sources(conn, str(run["id"])):
                    typer.echo(
                        f"  {str(item['status']).upper():7} {item['source_key']} "
                        f"errors={item['error_count']}"
                    )
    finally:
        conn.close()


if __name__ == "__main__":
    app()
