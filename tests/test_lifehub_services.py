import zipfile

import pytest

pytest.importorskip("wasmtime")
from academicos.lifehub.kernel import LifeHub  # noqa: E402
from academicos.lifehub.packages import PackageInstaller  # noqa: E402
from academicos.lifehub.store import LifeStore  # noqa: E402
from test_lifehub_wasm import _module  # noqa: E402


def test_exact_service_activation_binding_and_revocation(tmp_path):
    db, root = tmp_path / "hub.db", tmp_path / "installed"
    store = LifeStore(db)
    installer = PackageInstaller(root, store)
    try:
        for name, permissions, contribution in [
            ("caller", 'service_call = ["sample.provider:read"]', ""),
            (
                "provider",
                'storage_read = ["public"]',
                """
[[contributes]]
id = "read"
point = "lifehub.service"
entrypoint = "lifehub.wasm"
contract = "lifehub.core-wasm@1"
[contributes.config]
module = "reader.wasm"
""",
            ),
        ]:
            archive = tmp_path / f"{name}.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(
                    "plugin.toml",
                    f'''manifest_version = 1
api = "lifehub@1"
id = "sample.{name}"
name = "{name}"
version = "1.0.0"
[permissions]
{permissions}
{contribution}''',
                )
                output.writestr("reader.wasm", _module())
            installer.install(archive, approved_hash=installer.review(archive).content_hash)
    finally:
        store.close()
    hub = LifeHub(db_path=db, plugins_path=root)
    args = ("sample.caller", "sample.provider:read", "lifehub.core-wasm@1")
    try:
        assert hub.catalog(point="lifehub.service")["extensions"][0]["ref"] == args[1]
        with pytest.raises(PermissionError, match="not granted"):
            hub.activate_service(*args)
        with pytest.raises(ValueError, match="contract mismatch"):
            hub.grant_service(args[0], args[1], "lifehub.core-wasm@2")
        hub.grant_service(*args)
        with pytest.raises(PermissionError, match="cannot read"):
            hub.activate_service(*args)
        hub.grant_read("sample.provider", "public")
        assert hub.activate_service(*args) > 0
        with pytest.raises(PermissionError, match="did not request"):
            hub.activate_service("sample.provider", args[1], args[2])
        hub.revoke_service(*args)
        with pytest.raises(PermissionError, match="not granted"):
            hub.activate_service(*args)
        hub.grant_service(*args)
        (root / "sample.provider" / "reader.wasm").write_bytes(_module("private.today"))
        with pytest.raises(PermissionError, match="changed after approval"):
            hub.activate_service(*args)
        hub.revoke_service(*args)
        (root / "sample.provider" / "reader.wasm").write_bytes(_module())
        hub.grant_service(*args)
        hub.packages.uninstall("sample.provider")
        assert not any(g["capability"] == "service.activate" for g in hub.store.grants())
        with pytest.raises(KeyError):
            hub.activate_service(*args)
    finally:
        hub.close()
