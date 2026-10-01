from __future__ import annotations

import stat
import warnings
import zipfile
from pathlib import Path

import pytest

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.registry import PluginRegistry
from academicos.lifehub.store import LifeStore


MANIFEST = b"""manifest_version = 1
api = "lifehub@1"
id = "demo.package"
name = "Package"
version = "1.0.0"
[permissions]
storage_read = ["finance"]
storage_write = ["package"]
network_retrieval = ["example.com"]
localhost_ports = []
[[contributes]]
id = "card"
point = "workspace.widget"
entrypoint = "lifehub.primitive"
"""


def make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def test_review_install_and_tamper_revokes_activation(tmp_path: Path) -> None:
    archive = make_zip(tmp_path / "plugin.zip", {"plugin.toml": MANIFEST, "asset.txt": b"ok"})
    root = tmp_path / "installed"
    db = tmp_path / "hub.db"
    store = LifeStore(db)
    try:
        installer = PackageInstaller(root, store)
        review = installer.review(archive)
        assert review.manifest.permissions.storage_read == ["finance"]
        with pytest.raises(PermissionError, match="reviewed hash"):
            installer.install(archive, approved_hash="0" * 64)
        installer.install(archive, approved_hash=review.content_hash)
        with pytest.raises(PermissionError, match="requires approval verification"):
            PluginRegistry(root).discover()
        hub = LifeHub(db_path=db, plugins_path=root)
        try:
            assert hub.bundle("demo.package").manifest.version == "1.0.0"
            hub.grant_read("demo.package", "finance")
            old_store = hub.scoped_store("demo.package")
            old_gateway = hub.egress("demo.package")
            (root / "demo.package" / "asset.txt").write_bytes(b"changed")
            with pytest.raises(PermissionError, match="changed after approval"):
                hub.scoped_store("demo.package")
            with pytest.raises(PermissionError, match="changed after approval"):
                hub.extensions()
            with pytest.raises(PermissionError, match="changed after approval"):
                old_store.read("finance.today")
            with pytest.raises(PermissionError, match="changed after approval"):
                old_gateway.authorize("https://example.com/")
        finally:
            hub.close()
        (root / ".lifehub-managed").unlink()
        with pytest.raises(PermissionError, match="changed after approval"):
            LifeHub(db_path=db, plugins_path=root)
        installer.uninstall("demo.package")
        assert not store.grants("demo.package")
        assert not (root / "demo.package").exists()
    finally:
        store.close()


@pytest.mark.parametrize(
    "bad_name", ["../escape", "/absolute", "x/../../escape", "a\\b", "a//b", "./plugin.toml"]
)
def test_rejects_unsafe_archive_paths(tmp_path: Path, bad_name: str) -> None:
    archive = make_zip(tmp_path / "bad.zip", {"plugin.toml": MANIFEST, bad_name: b"bad"})
    store = LifeStore(":memory:")
    try:
        with pytest.raises(ValueError, match="invalid package entry"):
            PackageInstaller(tmp_path / "installed", store).review(archive)
    finally:
        store.close()


def test_rejects_zip_symlink_and_duplicate(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("plugin.toml", MANIFEST)
        symlink = zipfile.ZipInfo("link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        output.writestr(symlink, "../../secret")
    store = LifeStore(":memory:")
    try:
        installer = PackageInstaller(tmp_path / "installed", store)
        with pytest.raises(ValueError, match="non-regular"):
            installer.review(archive)
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("plugin.toml", MANIFEST)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                output.writestr("plugin.toml", MANIFEST)
        with pytest.raises(ValueError, match="duplicate"):
            installer.review(archive)
    finally:
        store.close()


def test_unapproved_directory_and_changed_manifest_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "installed"
    root.mkdir()
    (root / "other.txt").write_text("unmanaged")
    archive = make_zip(tmp_path / "plugin.zip", {"plugin.toml": MANIFEST})
    store = LifeStore(tmp_path / "hub.db")
    try:
        installer = PackageInstaller(root, store)
        with pytest.raises(ValueError, match="dedicated managed"):
            installer.install(archive, approved_hash=installer.review(archive).content_hash)
        (root / "other.txt").unlink()
        installer.install(archive, approved_hash=installer.review(archive).content_hash)
        (root / "demo.package" / "plugin.toml").write_bytes(MANIFEST.replace(b"package", b"hacked"))
        with pytest.raises(PermissionError):
            LifeHub(db_path=store.path, plugins_path=root)
    finally:
        store.close()
