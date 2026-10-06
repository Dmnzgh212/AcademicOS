import importlib.util
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

pytest.importorskip("wasmtime")
from academicos.lifehub.cli import app  # noqa: E402
from academicos.lifehub.packages import PackageInstaller  # noqa: E402
from academicos.lifehub.store import LifeStore  # noqa: E402


def test_shipped_echo_packages_through_cli(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/lifehub/json_echo/build.py"
    spec = importlib.util.spec_from_file_location("echo_builder", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    archives = module.build(tmp_path / "packages")
    db, root = tmp_path / "hub.db", tmp_path / "installed"
    runner = CliRunner()
    options = ["--db", str(db), "--installed", str(root)]
    for archive in archives:
        store = LifeStore(db)
        try:
            digest = PackageInstaller(root, store).review(archive).content_hash
        finally:
            store.close()
        result = runner.invoke(
            app, ["install-package", str(archive), "--approve-hash", digest, *options]
        )
        assert result.exit_code == 0, result.output
    args = ["example.client", "example.echo:echo"]
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"text": "中文", "value": 42}), encoding="utf-8")
    call = ["call-service", *args, "--request", str(request), *options]
    assert runner.invoke(app, call).exit_code != 0
    guest_call = ["run-wasm", "example.client:invoke", *options]
    assert runner.invoke(app, guest_call).exit_code != 0
    result = runner.invoke(app, ["review-service", *args, "lifehub.service-json@1", *options])
    assert result.exit_code == 0, result.output
    review = json.loads(result.output)
    result = runner.invoke(
        app,
        [
            "grant-service",
            *args,
            "lifehub.service-json@1",
            "--approve-hash",
            review["approval_digest"],
            *options,
        ],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, call)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"text": "中文", "value": 42}
    result = runner.invoke(app, guest_call)
    assert result.exit_code == 0, result.output
    assert "Result: 29" in result.output
    request.write_text("x" * 65537)
    result = runner.invoke(app, call)
    assert result.exit_code != 0
    assert "exceeds IO limit" in str(result.exception)
    request.write_text('{"value": NaN}')
    assert runner.invoke(app, call).exit_code != 0
    result = runner.invoke(app, ["revoke-service", *args, "lifehub.service-json@1", *options])
    assert result.exit_code == 0, result.output
    request.write_text("{}")
    assert runner.invoke(app, call).exit_code != 0
    assert runner.invoke(app, guest_call).exit_code != 0
