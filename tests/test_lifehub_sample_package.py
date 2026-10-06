"""Exercise the shipped sample through the actual CLI and kernel boundaries."""

import importlib.util
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

pytest.importorskip("wasmtime")

from academicos.lifehub.cli import app  # noqa: E402
from academicos.lifehub.kernel import LifeHub  # noqa: E402
from academicos.lifehub.packages import PackageInstaller  # noqa: E402
from academicos.lifehub.store import LifeStore  # noqa: E402


def test_sample_package_install_discover_execute_revoke_and_uninstall(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/lifehub/reader/build.py"
    spec = importlib.util.spec_from_file_location("sample_builder", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    archive = tmp_path / "reader.zip"
    module.build(archive)
    db, installed = tmp_path / "hub.db", tmp_path / "installed"
    store = LifeStore(db)
    try:
        digest = PackageInstaller(installed, store).review(archive).content_hash
    finally:
        store.close()
    runner = CliRunner()
    options = ["--db", str(db), "--plugins", str(installed)]
    result = runner.invoke(
        app,
        [
            "install-package",
            str(archive),
            "--approve-hash",
            digest,
            "--db",
            str(db),
            "--installed",
            str(installed),
        ],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["catalog", *options])
    assert result.exit_code == 0, result.output
    catalog = json.loads(result.output)
    assert catalog["extensions"][0]["contract"] == "lifehub.core-wasm@1"
    assert catalog["extensions"][0]["ref"] == "example.reader:read"
    hub = LifeHub(db_path=db, plugins_path=installed)
    try:
        assert hub.last_proposal_ids == []
        assert hub.last_effect_ids == []
        hub.store.append_record(
            plugin_id="host", namespace="sample.records", record_key="one", payload={"value": 42}
        )
        with pytest.raises(PermissionError, match="cannot read"):
            hub.run_wasm("example.reader:read")
        with pytest.raises(PermissionError, match="cannot read"):
            hub.read_records("example.reader", "sample.records")
        hub.grant_read("example.reader", "sample")
        assert hub.read_records("example.reader", "sample.records")["records"][0]["payload"] == {
            "value": 42
        }
        # Even an already open host must revalidate managed bytes for shell reads.
        module_path = hub.bundle("example.reader").root / "reader.wasm"
        approved = module_path.read_bytes()
        try:
            module_path.write_bytes(approved + b"tampered")
            with pytest.raises(PermissionError):
                hub.read_records("example.reader", "sample.records")
        finally:
            module_path.write_bytes(approved)
        assert hub.run_wasm("example.reader:read") > 0
        with pytest.raises(PermissionError, match="did not request"):
            hub.grant_read("example.reader", "private")
        hub.revoke_read("example.reader", "sample")
        with pytest.raises(PermissionError, match="cannot read"):
            hub.read_records("example.reader", "sample.records")
        with pytest.raises(PermissionError, match="cannot read"):
            hub.run_wasm("example.reader:read")
        hub.packages.uninstall("example.reader")
        assert hub.catalog()["extensions"] == []
        with pytest.raises(KeyError):
            hub.run_wasm("example.reader:read")
    finally:
        hub.close()
