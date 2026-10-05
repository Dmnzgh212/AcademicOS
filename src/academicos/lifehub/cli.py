from __future__ import annotations

from pathlib import Path
import json

import typer

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.effects import EffectService
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.proposals import ProposalService
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
            if name == "effect_request":
                formatted = ", ".join(f"{item['kind']} -> {item['destination']}" for item in values)
            else:
                formatted = ", ".join(map(str, values))
            typer.echo(f"  {name}: {formatted or 'none'}")
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


@app.command("run-wasm")
def run_wasm(
    ref: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Run one approved WebAssembly extension and stage its requests."""
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        typer.echo(f"Result: {hub.run_wasm(ref)}")
        if hub.last_proposal_ids:
            typer.echo(f"Pending proposals: {', '.join(map(str, hub.last_proposal_ids))}")
        if hub.last_effect_ids:
            typer.echo(f"Pending effects: {', '.join(map(str, hub.last_effect_ids))}")
    finally:
        hub.close()


@app.command("proposals")
def proposals(db: Path = typer.Option(DEFAULT_DB, "--db")) -> None:
    """Inspect full pending proposals before making a commit decision."""
    store = LifeStore(db)
    try:
        for item in ProposalService(store).list():
            typer.echo(
                f"#{item['id']} · {item['plugin_id']} · {item['extension_ref']} · "
                f"{item['namespace']}/{item['record_key']} · base={item['base_record_id']}"
            )
            typer.echo(f"  package: {item['package_hash']}")
            typer.echo(
                f"  payload: {json.dumps(item['payload'], ensure_ascii=False, sort_keys=True)}"
            )
    finally:
        store.close()


@app.command("approve-proposal")
def approve_proposal(
    proposal_id: int,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Commit one reviewed proposal if package authority and target version still match."""
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        typer.echo(f"Proposal #{proposal_id}: {hub.approve_proposal(proposal_id)}")
    finally:
        hub.close()


@app.command("reject-proposal")
def reject_proposal(
    proposal_id: int,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
) -> None:
    """Reject one pending proposal without reading or activating its package."""
    store = LifeStore(db)
    try:
        ProposalService(store).reject(proposal_id)
        typer.echo(f"Proposal #{proposal_id}: rejected")
    finally:
        store.close()


@app.command("effects")
def effects(
    status: str = typer.Option("pending", "--status"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
) -> None:
    """Inspect destination, purpose and full disclosure payload."""
    store = LifeStore(db)
    try:
        for item in EffectService(store).list(status):
            typer.echo(
                f"#{item['id']} · {item['status']} · {item['plugin_id']} · "
                f"{item['kind']} -> {item['destination']}"
            )
            typer.echo(f"  purpose: {item['purpose']}")
            typer.echo(f"  package: {item['package_hash']}")
            typer.echo(
                f"  payload: {json.dumps(item['payload'], sort_keys=True, ensure_ascii=False)}"
            )
    finally:
        store.close()


@app.command("approve-effect")
def approve_effect(
    request_id: int,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Approve one inspected disclosure request without executing it."""
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        hub.approve_effect(request_id)
        typer.echo(f"Effect #{request_id}: approved, not dispatched")
    finally:
        hub.close()


@app.command("reject-effect")
def reject_effect(request_id: int, db: Path = typer.Option(DEFAULT_DB, "--db")) -> None:
    """Reject an unattempted effect request."""
    store = LifeStore(db)
    try:
        EffectService(store).reject(request_id)
        typer.echo(f"Effect #{request_id}: rejected")
    finally:
        store.close()


@app.command("dispatch-fake-effect")
def dispatch_fake_effect(
    request_id: int,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Dispatch an approved test.record request to the local fake executor only."""
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        typer.echo(f"Effect #{request_id}: {hub.dispatch_effect(request_id)}")
    finally:
        hub.close()


@app.command("mark-effect-unknown")
def mark_effect_unknown(request_id: int, db: Path = typer.Option(DEFAULT_DB, "--db")) -> None:
    """Mark an interrupted in-flight request unknown after its worker has stopped."""
    store = LifeStore(db)
    try:
        EffectService(store).mark_unknown(request_id)
        typer.echo(f"Effect #{request_id}: unknown; no automatic retry")
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
                "  effect_request: "
                + (
                    ", ".join(
                        f"{item.kind} -> {item.destination}"
                        for item in manifest.permissions.effect_request
                    )
                    or "none"
                )
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
        items = hub.catalog(point=point)["extensions"]
        if not items:
            typer.echo("No extensions found.")
            return
        for item in items:
            typer.echo(
                f"{item['ref']} · point={item['point']} · "
                f"entry={item['entrypoint'] or 'declarative'}"
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
        typer.echo("NOTE approved core-Wasm extensions run without WASI")
        typer.echo("NOTE local proposals require a separate commit decision")
        typer.echo("NOTE arbitrary native code and external effects remain disabled")
    finally:
        hub.close()


if __name__ == "__main__":
    app()


@app.command("catalog")
def catalog(
    point: str | None = typer.Option(None, "--point"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    plugins: Path = typer.Option(DEFAULT_PLUGINS, "--plugins"),
) -> None:
    """Export the versioned JSON discovery contract for alternative local shells."""
    hub = LifeHub(db_path=db, plugins_path=plugins)
    try:
        typer.echo(json.dumps(hub.catalog(point=point), ensure_ascii=False))
    finally:
        hub.close()


@app.command("review-service")
def review_service(
    caller: str,
    ref: str,
    contract: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Inspect provider permissions and exact package snapshots before granting."""
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        typer.echo(json.dumps(hub.review_service(caller, ref, contract), ensure_ascii=False))
    finally:
        hub.close()


@app.command("grant-service")
def grant_service(
    caller: str,
    ref: str,
    contract: str,
    approve_hash: str = typer.Option(..., "--approve-hash"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Grant only the service snapshots explicitly reviewed by digest."""
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        hub.grant_service(caller, ref, contract, approved_digest=approve_hash)
        typer.echo("Service activation granted.")
    finally:
        hub.close()


@app.command("revoke-service")
def revoke_service(
    caller: str,
    ref: str,
    contract: str,
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Revoke matching service grants, including obsolete package bindings."""
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        hub.revoke_service(caller, ref, contract)
        typer.echo("Service activation revoked.")
    finally:
        hub.close()


@app.command("call-service")
def call_service(
    caller: str,
    ref: str,
    request_file: Path = typer.Option(..., "--request"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    installed: Path = typer.Option(DEFAULT_INSTALLED, "--installed"),
) -> None:
    """Call an authorized JSON computation service using a bounded local JSON file."""
    from academicos.lifehub.wasm import MAX_IO_BYTES, _invalid_json

    with request_file.open("rb") as source:
        raw = source.read(MAX_IO_BYTES + 1)
    if len(raw) > MAX_IO_BYTES:
        raise ValueError("service request file exceeds IO limit")
    request = json.loads(raw.decode("utf-8"), parse_constant=_invalid_json)
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        response = hub.call_service(caller, ref, request)
        typer.echo(json.dumps(response, ensure_ascii=False, allow_nan=False))
    finally:
        hub.close()
