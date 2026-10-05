import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("wasmtime")
from academicos.lifehub.kernel import LifeHub  # noqa: E402
from academicos.lifehub import kernel  # noqa: E402


@pytest.fixture
def echo_hub(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/lifehub/json_echo/build.py"
    spec = importlib.util.spec_from_file_location("echo_builder", source)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    hub = LifeHub(db_path=tmp_path / "hub.db", plugins_path=tmp_path / "installed")
    try:
        for archive in builder.build(tmp_path / "packages"):
            hub.packages.install(archive, approved_hash=hub.packages.review(archive).content_hash)
        args = ("example.client", "example.echo:echo", "lifehub.service-json@1")
        hub.grant_service(*args)
        yield hub, args
    finally:
        hub.close()


@pytest.mark.parametrize("change", ["revoke", "caller_bytes", "provider_bytes"])
def test_result_is_withheld_when_authority_changes_during_service(echo_hub, monkeypatch, change):
    hub, args = echo_hub
    original = kernel.run_json_service

    def intervening_run(module, request):
        output = original(module, request)
        if change == "revoke":
            hub.revoke_service(*args)
        else:
            plugin_id = args[0] if change == "caller_bytes" else "example.echo"
            root = hub.bundle(plugin_id).root
            (root / "unexpected.txt").write_text("changed while running")
        return output

    monkeypatch.setattr(kernel, "run_json_service", intervening_run)
    with pytest.raises(PermissionError, match="revoked|changed after approval"):
        hub.call_service(args[0], args[1], {"value": 1})
    assert hub.last_proposal_ids == []
    assert hub.last_effect_ids == []


def test_request_identity_fields_cannot_restore_revoked_authority(echo_hub):
    hub, args = echo_hub
    hub.revoke_service(*args)
    with pytest.raises(PermissionError, match="not granted"):
        hub.call_service(args[0], args[1], {"caller_id": "example.client", "granted": True})


def test_tampered_caller_is_rejected_before_service_execution(echo_hub):
    # Package integrity rejects an altered client before any guest code can start.
    hub, args = echo_hub
    root = hub.bundle(args[0]).root
    (root / "caller.wasm").write_bytes(b"forged module")
    with pytest.raises(PermissionError, match="changed after approval"):
        hub.run_wasm("example.client:invoke")
    assert hub.last_proposal_ids == []
    assert hub.last_effect_ids == []
