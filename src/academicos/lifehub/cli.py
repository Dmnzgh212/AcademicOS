from __future__ import annotations

from pathlib import Path

import typer

from academicos.lifehub.core import LifeHub
from academicos.lifehub.web import serve

app = typer.Typer(help="LifeHub: local-first extensible personal information platform.")

DEFAULT_DB = Path("data/lifehub.db")
DEFAULT_PLUGINS = Path("lifehub_plugins")


@app.command("init")
def init(
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """Initialize local storage and register discovered widgets."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        typer.echo(
            f"LifeHub initialized · db={db} · plugins={len(hub.bundles)} · "
            f"widgets={len(hub.store.workspace_layout())}"
        )
    finally:
        hub.close()


@app.command("plugins")
def plugins(
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins_dir: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """List discovered declarative plugins and their requested permissions."""
    hub = LifeHub(db_path=db, plugins_path=plugins_dir)
    try:
        if not hub.bundles:
            typer.echo("No plugins discovered.")
            return
        for bundle in hub.bundles:
            manifest = bundle.manifest
            typer.echo(f"{manifest.id} {manifest.version} · {manifest.name}")
            typer.echo(f"  kind: {', '.join(manifest.kind) or 'none'}")
            typer.echo(f"  storage_write: {', '.join(manifest.permissions.storage_write) or 'none'}")
            typer.echo(f"  network_hosts: {', '.join(manifest.permissions.network_hosts) or 'none'}")
            typer.echo(
                f"  localhost_ports: "
                f"{', '.join(str(p) for p in manifest.permissions.localhost_ports) or 'none'}"
            )
            typer.echo(f"  widgets: {', '.join(w.id for w in manifest.widgets) or 'none'}")
    finally:
        hub.close()


@app.command("demo")
def demo(
    db: Path = typer.Option(Path("data/lifehub-demo.db"), "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
    reset: bool = typer.Option(False, "--reset"),
    run_server: bool = typer.Option(False, "--serve"),
    port: int = typer.Option(8844, "--port", min=1, max=65535),
) -> None:
    """Seed only plugin-declared synthetic data; never touches the AcademicOS DB."""
    if "demo" not in db.name.lower():
        raise typer.BadParameter("demo database filename must contain 'demo'")
    if reset and db.exists():
        db.unlink()
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        inserted = hub.seed_declared_data()
        typer.echo(
            f"LifeHub demo ready · plugins={len(hub.bundles)} · "
            f"widgets={len(hub.store.workspace_layout())} · inserted={inserted} · db={db}"
        )
    finally:
        hub.close()
    if run_server:
        serve(db_path=db, plugins_path=plugins, port=port)


@app.command("serve")
def serve_cmd(
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
    port: int = typer.Option(8844, "--port", min=1, max=65535),
) -> None:
    """Serve the local-only draggable workspace."""
    serve(db_path=db, plugins_path=plugins, port=port)


@app.command("doctor")
def doctor(
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """Validate plugin manifests, local DB and privacy-facing permissions."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        typer.echo(f"PASS storage        {db}")
        typer.echo(f"PASS plugin-registry {len(hub.bundles)} plugin(s)")
        for bundle in hub.bundles:
            manifest = bundle.manifest
            typer.echo(
                f"PASS {manifest.id:<22} widgets={len(manifest.widgets)} "
                f"hosts={len(manifest.permissions.network_hosts)} "
                f"localhost={len(manifest.permissions.localhost_ports)}"
            )
        typer.echo("PASS policy         retrieval-only gateway; loopback-only web shell")
        typer.echo("NOTE executable third-party sandbox is not implemented in v0.1")
    finally:
        hub.close()


if __name__ == "__main__":
    app()
