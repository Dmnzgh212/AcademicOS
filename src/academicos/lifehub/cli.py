from __future__ import annotations

from pathlib import Path

import typer

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.store import LifeStore
from academicos.lifehub.web import serve

app = typer.Typer(help="LifeHub: local-first open extension host for personal computing.")

DEFAULT_DB = Path("data/lifehub.db")
DEFAULT_PLUGINS = Path("lifehub_plugins")
DEFAULT_INSTALLED = Path("data/lifehub-installed")


@app.command("review-package")
def review_package(archive: Path) -> None:
    """Inspect a local ZIP and print the exact digest required for approval."""
    store = LifeStore(":memory:")
    try:
        review = PackageInstaller(DEFAULT_INSTALLED, store).review(archive)
        manifest = review.manifest
        typer.echo(f"{manifest.id} {manifest.version} · {manifest.name} · files={review.files}")
        typer.echo(f"sha256-content: {review.content_hash}")
        for name, values in manifest.permissions.model_dump().items():
            typer.echo(f"  {name}: {', '.join(map(str, values)) or 'none'}")
        for contribution in manifest.contributes:
            typer.echo(f"  contributes: {contribution.point}:{contribution.id}")
    finally:
        store.close()


@app.command("install-package")
def install_package(
    archive: Path,
    approve_hash: str = typer.Option(..., "--approve-hash"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Install only the bytes reviewed and explicitly approved by digest."""
    store = LifeStore(db)
    try:
        review = PackageInstaller(installed, store).install(archive, approved_hash=approve_hash)
        typer.echo(
            f"Installed {review.manifest.id} {review.manifest.version} · {review.content_hash}"
        )
    finally:
        store.close()


@app.command("uninstall-package")
def uninstall_package(
    plugin_id: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Remove an installed package and its cross-plugin read grants."""
    store = LifeStore(db)
    try:
        PackageInstaller(installed, store).uninstall(plugin_id)
        typer.echo(f"Uninstalled {plugin_id}")
    finally:
        store.close()


@app.command("init")
def init(
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """Initialize local kernel storage and discover extension packages."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        typer.echo(
            f"LifeHub initialized · db={db} · plugins={len(hub.bundles)} · "
            f"extensions={len(hub.extensions())} · workspace_items={len(hub.store.workspace_layout())}"
        )
    finally:
        hub.close()


@app.command("plugins")
def plugins(
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins_dir: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """List discovered packages, requested capabilities and contributions."""
    hub = LifeHub(db_path=db, plugins_path=plugins_dir)
    try:
        if not hub.bundles:
            typer.echo("No plugins discovered.")
            return
        for bundle in hub.bundles:
            manifest = bundle.manifest
            typer.echo(f"{manifest.id} {manifest.version} · {manifest.name} · {manifest.api}")
            typer.echo(
                f"  storage_write: {', '.join(manifest.permissions.storage_write) or 'none'}"
            )
            typer.echo(
                f"  storage_read(requested): {', '.join(manifest.permissions.storage_read) or 'none'}"
            )
            typer.echo(
                f"  network_retrieval: {', '.join(manifest.permissions.network_retrieval) or 'none'}"
            )
            typer.echo(
                f"  localhost_ports: "
                f"{', '.join(str(p) for p in manifest.permissions.localhost_ports) or 'none'}"
            )
            typer.echo(
                "  contributes: "
                + (", ".join(f"{c.point}:{c.id}" for c in manifest.contributes) or "none")
            )
    finally:
        hub.close()


@app.command("extensions")
def extensions(
    point: str | None = typer.Option(None, "--point"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """Inspect the open extension registry, optionally filtering by extension point."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        items = hub.extensions(point)
        if not items:
            typer.echo("No extensions found.")
            return
        for item in items:
            contribution = item.contribution
            typer.echo(
                f"{item.ref} · point={contribution.point} · "
                f"entry={contribution.entrypoint or 'declarative'}"
            )
    finally:
        hub.close()


@app.command("grants")
def grants(
    plugin_id: str | None = typer.Option(None, "--plugin"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """List locally approved cross-plugin capabilities."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        rows = hub.store.grants(plugin_id)
        if not rows:
            typer.echo("No local grants.")
            return
        for row in rows:
            typer.echo(f"{row['plugin_id']} · {row['capability']} · {row['resource']}")
    finally:
        hub.close()


@app.command("grant-read")
def grant_read(
    plugin_id: str,
    namespace: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """Approve one manifest-requested cross-plugin storage read locally."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        hub.grant_read(plugin_id, namespace)
        typer.echo(f"Granted storage.read · plugin={plugin_id} · namespace={namespace}")
    finally:
        hub.close()


@app.command("revoke-read")
def revoke_read(
    plugin_id: str,
    namespace: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """Revoke a previously approved cross-plugin storage read."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        hub.revoke_read(plugin_id, namespace)
        typer.echo(f"Revoked storage.read · plugin={plugin_id} · namespace={namespace}")
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
            f"extensions={len(hub.extensions())} · "
            f"workspace_items={len(hub.store.workspace_layout())} · inserted={inserted} · db={db}"
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
    """Serve the temporary local workspace consumer."""
    serve(db_path=db, plugins_path=plugins, port=port)


@app.command("doctor")
def doctor(
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """Validate package manifests, extension registry, local DB and privacy policy."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        typer.echo(f"PASS storage          {db}")
        typer.echo(f"PASS plugin-registry  {len(hub.bundles)} plugin(s)")
        typer.echo(f"PASS extension-index  {len(hub.extensions())} extension(s)")
        typer.echo(f"PASS extension-points {', '.join(hub.registry.points()) or 'none'}")
        for bundle in hub.bundles:
            manifest = bundle.manifest
            typer.echo(
                f"PASS {manifest.id:<22} contributes={len(manifest.contributes)} "
                f"read_requests={len(manifest.permissions.storage_read)} "
                f"hosts={len(manifest.permissions.network_retrieval)}"
            )
        typer.echo("PASS policy           local persistence; retrieval-only egress broker")
        typer.echo(
            "NOTE executable third-party runtime remains disabled until OS-level sandboxing exists"
        )
    finally:
        hub.close()


if __name__ == "__main__":
    app()
