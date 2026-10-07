from __future__ import annotations

import json
from pathlib import Path

import pytest

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.manifest import load_manifest
from academicos.lifehub.network import EgressGateway
from academicos.lifehub.registry import PluginRegistry
from academicos.lifehub.shells.reference_web import render_workspace


def _write_plugin(
    root: Path,
    *,
    folder: str = "sample",
    plugin_id: str = "demo.sample",
    writes: str = "sample",
    reads: str | None = None,
) -> Path:
    plugin = root / folder
    plugin.mkdir(parents=True)
    read_line = f'storage_read = ["{reads}"]' if reads else "storage_read = []"
    (plugin / "plugin.toml").write_text(
        f"""
manifest_version = 1
api = "lifehub@1"
id = "{plugin_id}"
name = "Sample"
version = "0.2.0"

[permissions]
{read_line}
storage_write = ["{writes}"]
network_retrieval = ["example.com"]
localhost_ports = [8000]

[[contributes]]
id = "main"
point = "workspace.widget"
title = "Sample surface"
entrypoint = "lifehub.primitive"

[contributes.config]
namespace = "{writes}.today"
renderer = "list"
width = 5
height = 4
limit = 5
default_workspace = true

[[contributes]]
id = "future"
point = "future.capability.that-core-does-not-know"
entrypoint = "sample.future"
""".strip(),
        encoding="utf-8",
    )
    (plugin / "seed.json").write_text(
        json.dumps(
            [
                {
                    "namespace": f"{writes}.today",
                    "record_key": "today",
                    "payload": {"items": [{"title": "Local item", "detail": "stored locally"}]},
                    "source": "synthetic",
                }
            ]
        ),
        encoding="utf-8",
    )
    return plugin


def test_registry_accepts_unknown_extension_points_without_core_changes(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    registry = PluginRegistry(plugins)

    assert registry.points() == (
        "future.capability.that-core-does-not-know",
        "workspace.widget",
    )
    assert registry.extension("demo.sample:future").contribution.entrypoint == "sample.future"


def test_store_workspace_and_temporary_shell_are_extension_driven(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    hub = LifeHub(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        assert [bundle.manifest.id for bundle in hub.bundles] == ["demo.sample"]
        assert len(hub.extensions()) == 2
        assert hub.seed_declared_data() == 1
        assert hub.seed_declared_data() == 0
        assert hub.store.workspace_layout() == []
        page = render_workspace(hub, token="test-token")
        layout = hub.store.workspace_layout()
        assert layout[0]["extension_ref"] == "demo.sample:main"
        assert layout[0]["width"] == 5
        assert layout[0]["height"] == 4
        assert "Sample surface" in page
        assert "Local item" in page
        assert "stored locally" in page
        assert "future.capability.that-core-does-not-know" not in page
    finally:
        hub.close()


def test_scoped_store_cannot_write_another_namespace(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    hub = LifeHub(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        scoped = hub.scoped_store("demo.sample")
        assert scoped.append("sample.private", "one", {"value": 1})
        with pytest.raises(PermissionError, match="cannot write namespace"):
            scoped.append("finance.private", "leak", {"value": 2})
    finally:
        hub.close()


def test_cross_plugin_read_requires_manifest_request_and_local_grant(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, folder="producer", plugin_id="demo.producer", writes="finance")
    _write_plugin(
        plugins,
        folder="consumer",
        plugin_id="demo.consumer",
        writes="consumer",
        reads="finance",
    )
    hub = LifeHub(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        assert hub.seed_declared_data() == 2
        consumer = hub.scoped_store("demo.consumer")
        with pytest.raises(PermissionError, match="cannot read namespace"):
            consumer.read("finance.today")

        hub.grant_read("demo.consumer", "finance")
        rows = consumer.read("finance.today")
        assert rows[0]["payload"]["items"][0]["title"] == "Local item"

        hub.revoke_read("demo.consumer", "finance")
        with pytest.raises(PermissionError):
            consumer.read("finance.today")
    finally:
        hub.close()


def test_kernel_refuses_grant_not_requested_by_manifest(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    hub = LifeHub(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        with pytest.raises(PermissionError, match="did not request"):
            hub.grant_read("demo.sample", "finance")
    finally:
        hub.close()


def test_egress_gateway_is_retrieval_only_and_allowlisted(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    hub = LifeHub(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        manifest = hub.bundles[0].manifest
        gateway = EgressGateway(hub.store, manifest)
        gateway.authorize("https://example.com/menu")
        gateway.authorize("http://localhost:8000/api")

        with pytest.raises(PermissionError, match="retrieval-only"):
            gateway.authorize("https://example.com/upload", method="POST")
        with pytest.raises(PermissionError, match="allowlisted"):
            gateway.authorize("https://evil.example/menu")
        with pytest.raises(PermissionError, match="must use https"):
            gateway.authorize("http://example.com/menu")
        with pytest.raises(PermissionError, match="port 9000"):
            gateway.authorize("http://localhost:9000/api")
        with pytest.raises(PermissionError, match="query strings"):
            gateway.authorize("https://example.com/menu?secret=local-data")

        rows = hub.store.conn.execute(
            "SELECT allowed FROM lifehub_network_audit ORDER BY id"
        ).fetchall()
        assert [row["allowed"] for row in rows] == [1, 1, 0, 0, 0, 0, 0]
    finally:
        hub.close()


def test_legacy_v01_manifest_is_upgraded_at_boundary(tmp_path: Path) -> None:
    path = tmp_path / "plugin.toml"
    path.write_text(
        """
id = "legacy.sample"
name = "Legacy"
version = "0.1.0"
kind = ["widget"]
[permissions]
storage_write = ["legacy"]
network_hosts = []
localhost_ports = []
[[widgets]]
id = "old"
title = "Old card"
namespace = "legacy.today"
renderer = "list"
""".strip(),
        encoding="utf-8",
    )
    manifest = load_manifest(path)
    assert manifest.manifest_version == 1
    assert manifest.api == "lifehub@1"
    assert manifest.contributes[0].point == "workspace.widget"
    assert manifest.contributes[0].config["renderer"] == "list"
