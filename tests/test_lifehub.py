from __future__ import annotations

import json
from pathlib import Path

import pytest

from academicos.lifehub.core import EgressGateway, LifeHub, PluginRegistry
from academicos.lifehub.web import render_workspace


def _write_plugin(root: Path) -> Path:
    plugin = root / "sample"
    plugin.mkdir(parents=True)
    (plugin / "plugin.toml").write_text(
        """
id = "demo.sample"
name = "Sample"
version = "0.1.0"
kind = ["connector", "widget"]

[permissions]
storage_write = ["sample"]
network_hosts = ["example.com"]
localhost_ports = [8000]

[[widgets]]
id = "main"
title = "Sample widget"
namespace = "sample.today"
renderer = "list"
width = 1
height = 1
limit = 5
""".strip(),
        encoding="utf-8",
    )
    (plugin / "seed.json").write_text(
        json.dumps(
            [
                {
                    "namespace": "sample.today",
                    "record_key": "today",
                    "payload": {"items": [{"title": "Local item", "detail": "stored locally"}]},
                    "source": "synthetic",
                }
            ]
        ),
        encoding="utf-8",
    )
    return plugin


def test_registry_store_and_workspace_are_plugin_driven(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    hub = LifeHub(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        assert [bundle.manifest.id for bundle in hub.bundles] == ["demo.sample"]
        assert hub.seed_declared_data() == 1
        assert hub.seed_declared_data() == 0
        layout = hub.store.workspace_layout()
        assert layout[0]["widget_id"] == "main"
        page = render_workspace(hub, token="test-token")
        assert "Sample widget" in page
        assert "Local item" in page
        assert "stored locally" in page
    finally:
        hub.close()


def test_scoped_store_cannot_write_another_namespace(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    registry = PluginRegistry(plugins)
    manifest = registry.discover()[0].manifest
    hub = LifeHub(db_path=tmp_path / "lifehub.db", plugins_path=plugins)
    try:
        scoped = hub.store.scoped(manifest)
        assert scoped.append("sample.private", "one", {"value": 1})
        with pytest.raises(PermissionError, match="cannot write namespace"):
            scoped.append("finance.private", "leak", {"value": 2})
    finally:
        hub.close()


def test_registry_rejects_widget_outside_owned_namespace(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    plugin = _write_plugin(plugins)
    path = plugin / "plugin.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("sample.today", "other.today"), encoding="utf-8")
    with pytest.raises(ValueError, match="does not own"):
        PluginRegistry(plugins).discover()


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

        rows = hub.store.conn.execute(
            "SELECT allowed FROM lifehub_network_audit ORDER BY id"
        ).fetchall()
        assert [row["allowed"] for row in rows] == [1, 1, 0, 0, 0, 0]
    finally:
        hub.close()
