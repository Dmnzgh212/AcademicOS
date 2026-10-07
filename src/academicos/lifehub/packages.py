"""Review and install inert plugin packages into an approval-gated directory."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.store import LifeStore

MAX_FILES = 256
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PACKAGE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class PackageReview:
    manifest: PluginManifest
    content_hash: str
    files: int


def _digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        path = name.encode("utf-8")
        digest.update(len(path).to_bytes(4, "big"))
        digest.update(path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _safe_name(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return (
        bool(parts)
        and PurePosixPath(name).as_posix() == name
        and all(part not in ("", ".", "..") for part in parts)
        and not (name.startswith("/") or "\\" in name or ":" in name or "\x00" in name)
    )


def _archive_files(path: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    size = 0
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES:
            raise ValueError("too many package entries")
        for entry in entries:
            name = entry.filename
            if not _safe_name(name) or entry.is_dir():
                raise ValueError(f"invalid package entry: {name!r}")
            mode = (entry.external_attr >> 16) & 0o170000
            if mode not in (0, stat.S_IFREG):
                raise ValueError(f"non-regular package entry: {name!r}")
            if name in files or entry.file_size > MAX_FILE_BYTES:
                raise ValueError(f"duplicate or oversized package entry: {name!r}")
            size += entry.file_size
            if size > MAX_PACKAGE_BYTES:
                raise ValueError("package exceeds size limit")
            with archive.open(entry) as stream:
                content = stream.read(MAX_FILE_BYTES + 1)
            if len(content) != entry.file_size:
                raise ValueError(f"invalid package entry size: {name!r}")
            files[name] = content
    return files


def _directory_files(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    size = 0
    for current, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            item = Path(current) / name
            if item.is_symlink():
                raise PermissionError(f"package contains symlink: {item}")
        for name in names:
            item = Path(current) / name
            if not item.is_file():
                raise PermissionError(f"package contains non-file: {item}")
            relative = item.relative_to(root).as_posix()
            if (
                not _safe_name(relative)
                or len(files) >= MAX_FILES
                or item.stat().st_size > MAX_FILE_BYTES
            ):
                raise PermissionError("invalid installed package contents")
            content = item.read_bytes()
            size += len(content)
            if size > MAX_PACKAGE_BYTES:
                raise PermissionError("installed package exceeds size limit")
            files[relative] = content
    return files


class PackageInstaller:
    def __init__(self, root: str | Path, store: LifeStore) -> None:
        self.root = Path(root)
        self.store = store

    def is_managed(self) -> bool:
        return (
            self.store.conn.execute(
                "SELECT 1 FROM lifehub_managed_roots WHERE path=?", (str(self.root.resolve()),)
            ).fetchone()
            is not None
        )

    def review(self, archive: str | Path) -> PackageReview:
        files = _archive_files(Path(archive))
        if "plugin.toml" not in files:
            raise ValueError("package must contain plugin.toml at its root")
        payload = tomllib.loads(files["plugin.toml"].decode("utf-8"))
        if "manifest_version" not in payload:
            raise ValueError("installable packages require a versioned manifest")
        manifest = PluginManifest.model_validate(payload)
        return PackageReview(manifest, _digest(files), len(files))

    def install(self, archive: str | Path, *, approved_hash: str) -> PackageReview:
        review = self.review(archive)
        if review.content_hash != approved_hash:
            raise PermissionError("package contents differ from reviewed hash")
        marker = self.root / ".lifehub-managed"
        if self.root.exists() and not marker.is_file() and any(self.root.iterdir()):
            raise ValueError("install into a dedicated managed plugin directory")
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / review.manifest.id
        if (
            destination.exists()
            or self.store.conn.execute(
                "SELECT 1 FROM lifehub_installed_packages WHERE plugin_id=?", (review.manifest.id,)
            ).fetchone()
        ):
            raise ValueError(f"plugin already installed: {review.manifest.id}")
        files = _archive_files(Path(archive))
        if _digest(files) != approved_hash:
            raise PermissionError("package changed during installation")
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=self.root))
        try:
            for name, content in files.items():
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            if _digest(_directory_files(staging)) != approved_hash:
                raise PermissionError("staged package changed")
            marker.touch(exist_ok=True)
            staging.rename(destination)
            try:
                with self.store.conn:
                    self.store.conn.execute(
                        "INSERT OR IGNORE INTO lifehub_managed_roots(path) VALUES (?)",
                        (str(self.root.resolve()),),
                    )
                    self.store.conn.execute(
                        "INSERT INTO lifehub_installed_packages VALUES (?, ?, ?, ?)",
                        (
                            review.manifest.id,
                            review.manifest.version,
                            approved_hash,
                            datetime.now(UTC).isoformat(),
                        ),
                    )
            except BaseException:
                shutil.rmtree(destination)
                raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return review

    def verify(self, root: Path, manifest: PluginManifest) -> None:
        self.approved_files(root, manifest)

    def approved_files(self, root: Path, manifest: PluginManifest) -> dict[str, bytes]:
        """Return one verified snapshot so callers need not reopen an asset after checking it."""
        if root.is_symlink() or root.name != manifest.id:
            raise PermissionError(f"invalid installed plugin path: {root}")
        row = self.store.conn.execute(
            "SELECT version, content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
            (manifest.id,),
        ).fetchone()
        if row is None or row["version"] != manifest.version:
            raise PermissionError(f"plugin has no matching approval: {manifest.id}")
        files = _directory_files(root)
        if _digest(files) != row["content_hash"]:
            raise PermissionError(f"installed plugin changed after approval: {manifest.id}")
        return files

    def uninstall(self, plugin_id: str) -> None:
        row = self.store.conn.execute(
            "SELECT 1 FROM lifehub_installed_packages WHERE plugin_id=?", (plugin_id,)
        ).fetchone()
        if row is None:
            raise KeyError(plugin_id)
        destination = self.root / plugin_id
        with self.store.conn:
            # Remove incoming grants too: identical reinstall must not revive authority.
            for grant in self.store.grants():
                if grant["capability"] not in {"service.activate", "component.interface"}:
                    continue
                binding = json.loads(grant["resource"])
                provider_ref = binding[2] if grant["capability"] == "component.interface" else binding[0]
                if provider_ref.split(":", 1)[0] == plugin_id:
                    self.store.conn.execute(
                        "DELETE FROM lifehub_permission_grants "
                        "WHERE plugin_id=? AND capability=? AND resource=?",
                        (grant["plugin_id"], grant["capability"], grant["resource"]),
                    )
            self.store.conn.execute(
                """UPDATE lifehub_change_proposals SET status='invalidated', decided_at=?
                WHERE plugin_id=? AND status='pending'""",
                (datetime.now(UTC).isoformat(), plugin_id),
            )
            self.store.conn.execute(
                """UPDATE lifehub_effect_requests SET status='invalidated', resolved_at=?
                WHERE plugin_id=? AND status IN ('pending', 'approved')""",
                (datetime.now(UTC).isoformat(), plugin_id),
            )
            self.store.conn.execute(
                "DELETE FROM lifehub_installed_packages WHERE plugin_id=?", (plugin_id,)
            )
            self.store.conn.execute(
                "DELETE FROM lifehub_permission_grants WHERE plugin_id=?", (plugin_id,)
            )
        if destination.is_symlink():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination)
