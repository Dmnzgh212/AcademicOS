from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from academicos.lifehub.control import CONTROL_API, EngineController
from academicos.lifehub.engine import ExecutionState, LifeHubEngine, RunnerStart
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.store import LifeStore


class _RouteRunner:
    id = "test.route"

    def start(self, engine, component):
        return RunnerStart(ExecutionState.RUNNING, handle=component.ref)

    def stop(self, engine, component, handle):
        return None


def _archive(path: Path, manifest: str) -> Path:
    with zipfile.ZipFile(path, "w") as output:
        output.writestr("plugin.toml", manifest.strip())
    return path


def _install_pair(tmp_path: Path) -> tuple[Path, Path]:
    consumer = _archive(
        tmp_path / "consumer.zip",
        """
manifest_version = 1
api = "lifehub@1"
id = "demo.consumer"
name = "Consumer"
version = "1.0.0"

[[components]]
id = "worker"
runner = "test.route"
requires = ["example.echo@1"]
""",
    )
    provider = _archive(
        tmp_path / "provider.zip",
        """
manifest_version = 1
api = "lifehub@1"
id = "demo.provider"
name = "Provider"
version = "1.0.0"

[[components]]
id = "echo"
runner = "test.route"
provides = ["example.echo@1"]
""",
    )
    installed = tmp_path / "installed"
    db = tmp_path / "lifehub.db"
    store = LifeStore(db)
    try:
        installer = PackageInstaller(installed, store)
        for archive in (consumer, provider):
            review = installer.review(archive)
            installer.install(archive, approved_hash=review.content_hash)
    finally:
        store.close()
    return installed, db


def test_required_interface_denies_start_until_snapshot_bound_route_is_granted(
    tmp_path: Path,
) -> None:
    installed, db = _install_pair(tmp_path)
    engine = LifeHubEngine(db_path=db, plugins_path=installed)
    engine.register_runner(_RouteRunner())
    consumer = "demo.consumer:worker"
    provider = "demo.provider:echo"
    interface = "example.echo@1"
    try:
        with pytest.raises(PermissionError, match="no granted provider"):
            engine.start(consumer)

        review = engine.routes.review(consumer, interface, provider)
        assert review["granted"] is False
        assert len(review["consumer_digest"]) == 64
        assert len(review["provider_digest"]) == 64

        with pytest.raises(PermissionError, match="review changed"):
            engine.routes.grant(
                consumer,
                interface,
                provider,
                approved_digest="0" * 64,
            )

        route = engine.routes.grant(
            consumer,
            interface,
            provider,
            approved_digest=review["approval_digest"],
        )
        assert route.provider_ref == provider
        assert engine.routes.resolve(consumer, interface) == route

        started = engine.start(consumer)
        assert started.state == ExecutionState.RUNNING

        assert engine.routes.revoke(consumer, interface, provider) == 1
        with pytest.raises(PermissionError, match="no granted provider"):
            engine.routes.resolve(consumer, interface)
        with pytest.raises(PermissionError, match="no granted provider"):
            engine.start(consumer)

        # Revocation blocks new authority use but does not fake-kill an already
        # running runner; lifecycle policy is a separate Engine concern.
        assert engine.stop(started.execution_id).state == ExecutionState.STOPPED
    finally:
        engine.close()


def test_route_cannot_grant_undeclared_consumer_or_provider_interface(tmp_path: Path) -> None:
    installed, db = _install_pair(tmp_path)
    engine = LifeHubEngine(db_path=db, plugins_path=installed)
    try:
        with pytest.raises(PermissionError, match="did not declare"):
            engine.routes.review(
                "demo.consumer:worker",
                "example.other@1",
                "demo.provider:echo",
            )
        with pytest.raises(PermissionError, match="does not provide"):
            engine.routes.review(
                "demo.consumer:worker",
                "example.echo@1",
                "demo.consumer:worker",
            )
    finally:
        engine.close()


def test_route_binding_fails_closed_when_provider_package_snapshot_changes(
    tmp_path: Path,
) -> None:
    installed, db = _install_pair(tmp_path)
    engine = LifeHubEngine(db_path=db, plugins_path=installed)
    consumer = "demo.consumer:worker"
    provider = "demo.provider:echo"
    interface = "example.echo@1"
    try:
        review = engine.routes.review(consumer, interface, provider)
        engine.routes.grant(
            consumer,
            interface,
            provider,
            approved_digest=review["approval_digest"],
        )
        assert engine.routes.resolve(consumer, interface).provider_ref == provider

        (installed / "demo.provider" / "tampered.txt").write_text(
            "changed after approval", encoding="utf-8"
        )
        with pytest.raises(PermissionError):
            engine.routes.resolve(consumer, interface)
    finally:
        engine.close()


def test_revoke_works_without_recomputing_current_provider_binding(tmp_path: Path) -> None:
    installed, db = _install_pair(tmp_path)
    engine = LifeHubEngine(db_path=db, plugins_path=installed)
    consumer = "demo.consumer:worker"
    provider = "demo.provider:echo"
    interface = "example.echo@1"
    try:
        review = engine.routes.review(consumer, interface, provider)
        engine.routes.grant(
            consumer,
            interface,
            provider,
            approved_digest=review["approval_digest"],
        )
        (installed / "demo.provider" / "tampered.txt").write_text("changed", encoding="utf-8")
        assert engine.routes.revoke(consumer, interface, provider) == 1
    finally:
        engine.close()


def test_local_control_plane_manages_reviewed_interface_routes(tmp_path: Path) -> None:
    installed, db = _install_pair(tmp_path)
    engine = LifeHubEngine(db_path=db, plugins_path=installed)
    controller = EngineController(engine)
    consumer = "demo.consumer:worker"
    provider = "demo.provider:echo"
    interface = "example.echo@1"

    def request(op: str, **payload):
        return controller.handle({"api": CONTROL_API, "op": op, **payload})

    try:
        denied = request("route-resolve", consumer=consumer, interface=interface)
        assert denied["ok"] is False

        review = request(
            "route-review",
            consumer=consumer,
            interface=interface,
            provider=provider,
        )
        assert review["ok"] is True
        approval = review["result"]["approval_digest"]

        granted = request(
            "route-grant",
            consumer=consumer,
            interface=interface,
            provider=provider,
            approval_digest=approval,
        )
        assert granted["ok"] is True
        assert granted["result"]["provider_ref"] == provider

        resolved = request("route-resolve", consumer=consumer, interface=interface)
        assert resolved["ok"] is True
        assert resolved["result"]["provider_ref"] == provider

        revoked = request(
            "route-revoke",
            consumer=consumer,
            interface=interface,
            provider=provider,
        )
        assert revoked == {"api": CONTROL_API, "ok": True, "result": {"revoked": 1}}

        denied_again = request("route-resolve", consumer=consumer, interface=interface)
        assert denied_again["ok"] is False
    finally:
        engine.close()
