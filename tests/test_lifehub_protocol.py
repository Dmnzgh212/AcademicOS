import json

import pytest

from academicos.lifehub.kernel import LifeHub
from test_lifehub import _write_plugin


def test_catalog_supports_alternative_shells_without_exposing_host_paths(tmp_path):
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    hub = LifeHub(db_path=tmp_path / "hub.db", plugins_path=plugins)
    try:
        catalog = hub.catalog(point="future.capability.that-core-does-not-know")
        assert catalog["api"] == "lifehub.catalog@1"
        assert [x["ref"] for x in catalog["extensions"]] == ["demo.sample:future"]
        assert str(tmp_path) not in json.dumps(catalog)
        assert "requested_permissions" in catalog["packages"][0]
        catalog["extensions"][0]["config"]["injected"] = True
        catalog["packages"][0]["requested_permissions"]["storage_write"].append("finance")
        assert "injected" not in hub.extension("demo.sample:future").contribution.config
        with pytest.raises(PermissionError):
            hub.scoped_store("demo.sample").append("finance", "one", {})
        with pytest.raises(ValueError, match="unsupported catalog API"):
            hub.catalog(api="lifehub.catalog@2")
    finally:
        hub.close()


def test_unknown_wasm_contract_rejected_before_execution(tmp_path):
    plugins = tmp_path / "plugins"
    plugin = _write_plugin(plugins)
    path = plugin / "plugin.toml"
    path.write_text(
        path.read_text().replace(
            'entrypoint = "sample.future"',
            'entrypoint = "lifehub.wasm"\ncontract = "lifehub.core-wasm@2"',
        )
    )
    hub = LifeHub(db_path=tmp_path / "hub.db", plugins_path=plugins)
    try:
        assert hub.catalog()["extensions"][1]["contract"] == "lifehub.core-wasm@2"
        with pytest.raises(ValueError, match="unsupported extension contract"):
            hub.run_wasm("demo.sample:future")
    finally:
        hub.close()


def test_cli_catalog_exports_json_contract(tmp_path):
    from typer.testing import CliRunner
    from academicos.lifehub.cli import app

    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    result = CliRunner().invoke(
        app,
        [
            "catalog",
            "--db",
            str(tmp_path / "hub.db"),
            "--plugins",
            str(plugins),
            "--point",
            "future.capability.that-core-does-not-know",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["api"] == "lifehub.catalog@1"
    assert [x["ref"] for x in payload["extensions"]] == ["demo.sample:future"]


def test_web_shell_skips_incompatible_primitive_contract(tmp_path):
    from academicos.lifehub.web import render_workspace

    plugins = tmp_path / "plugins"
    plugin = _write_plugin(plugins)
    path = plugin / "plugin.toml"
    path.write_text(
        path.read_text().replace(
            'entrypoint = "lifehub.primitive"',
            'entrypoint = "lifehub.primitive"\ncontract = "lifehub.primitive@2"',
        )
    )
    hub = LifeHub(db_path=tmp_path / "hub.db", plugins_path=plugins)
    try:
        hub.seed_declared_data()
        page = render_workspace(hub, token="test-token")
        assert "Unsupported surface contract" in page
        assert "Local item" not in page
    finally:
        hub.close()


def test_catalog_uses_one_discovery_result_and_refreshes_next_request(tmp_path, monkeypatch):
    from academicos.lifehub.protocol import build_catalog
    from academicos.lifehub.registry import PluginRegistry

    plugin = _write_plugin(tmp_path)
    manifest_path = plugin / "plugin.toml"
    original = manifest_path.read_text()
    registry = PluginRegistry(tmp_path, managed=True, verify=lambda root, manifest: None)
    discover = registry.discover
    scans = []

    def discover_then_update():
        bundles = discover()
        scans.append(bundles)
        if len(scans) == 1:
            manifest_path.write_text(original.replace('sample.future', 'sample.updated'))
        return bundles

    monkeypatch.setattr(registry, "discover", discover_then_update)
    first = build_catalog(registry)
    assert len(scans) == 1
    assert first["extensions"][1]["entrypoint"] == "sample.future"
    assert all(item["plugin_id"] == first["packages"][0]["id"]
               for item in first["extensions"])
    second = build_catalog(registry, point="future.capability.that-core-does-not-know")
    assert len(scans) == 2
    assert second["extensions"][0]["entrypoint"] == "sample.updated"
    assert first["extensions"][1]["entrypoint"] == "sample.future"


def test_platform_discovery_does_not_interpret_shell_layout(tmp_path):
    plugins = tmp_path / "plugins"
    plugin = _write_plugin(plugins)
    manifest = plugin / "plugin.toml"
    manifest.write_text(manifest.read_text().replace("width = 5", 'width = "custom-shell-value"'))
    hub = LifeHub(db_path=tmp_path / "hub.db", plugins_path=plugins)
    try:
        assert hub.store.workspace_layout() == []
        assert hub.catalog()["extensions"][0]["config"]["width"] == "custom-shell-value"
        assert hub.store.workspace_layout() == []
    finally:
        hub.close()
