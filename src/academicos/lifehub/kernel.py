from __future__ import annotations

import json
from pathlib import Path

from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.network import EgressGateway
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.registry import PluginBundle, PluginRegistry, RegisteredExtension
from academicos.lifehub.store import LifeStore, namespace_allowed
from academicos.lifehub.wasm import WasmRunner


class LifeHub:
    """LifeHub extension kernel.

    The kernel deliberately knows as little as possible about product domains. It
    discovers plugin packages, indexes arbitrary extension points, brokers local
    capabilities, and owns the privacy boundary.
    """

    def __init__(
        self,
        *,
        db_path: str | Path = "data/lifehub.db",
        plugins_path: str | Path = "lifehub_plugins",
    ) -> None:
        self.store = LifeStore(db_path)
        self.packages = PackageInstaller(plugins_path, self.store)
        self.registry = PluginRegistry(
            plugins_path, verify=self.packages.verify, managed=self.packages.is_managed()
        )
        self.registry.discover()
        self.store.sync_workspace_extensions(self.registry)

    @property
    def bundles(self) -> tuple[PluginBundle, ...]:
        return self.registry.discover()

    def close(self) -> None:
        self.store.close()

    def bundle(self, plugin_id: str) -> PluginBundle:
        return self.registry.bundle(plugin_id)

    def extension(self, ref: str) -> RegisteredExtension:
        return self.registry.extension(ref)

    def extensions(self, point: str | None = None) -> tuple[RegisteredExtension, ...]:
        return self.registry.extensions(point)

    def scoped_store(self, plugin_id: str):  # noqa: ANN201
        return self.store.scoped(
            self.bundle(plugin_id).manifest, verify=lambda: self.bundle(plugin_id)
        )

    def egress(self, plugin_id: str) -> EgressGateway:
        return EgressGateway(
            self.store, self.bundle(plugin_id).manifest, verify=lambda: self.bundle(plugin_id)
        )

    def run_wasm(self, ref: str) -> int:
        """Run one approved, read-only WebAssembly contribution without WASI."""
        extension = self.extension(ref)
        bundle = self.bundle(extension.plugin_id)
        if extension.contribution.entrypoint != "lifehub.wasm":
            raise ValueError(f"extension is not a WebAssembly entrypoint: {ref}")
        if not self.packages.is_managed():
            raise PermissionError("WebAssembly execution requires an installed, approved package")
        module_name = extension.contribution.config.get("module")
        if not isinstance(module_name, str) or not module_name.endswith(".wasm"):
            raise ValueError("WebAssembly contribution needs a .wasm module path")
        files = self.packages.approved_files(bundle.root, bundle.manifest)
        if module_name not in files:
            raise ValueError("WebAssembly module is not in the approved package")
        return WasmRunner(self.scoped_store(extension.plugin_id)).run(files[module_name])

    def grant_read(self, plugin_id: str, namespace: str) -> None:
        manifest = self.bundle(plugin_id).manifest
        if namespace_allowed(namespace, manifest.permissions.storage_write):
            return
        if not namespace_allowed(namespace, manifest.permissions.storage_read):
            raise PermissionError(
                f"plugin {plugin_id} did not request storage.read for namespace {namespace!r}"
            )
        self.store.grant(plugin_id, "storage.read", namespace)

    def revoke_read(self, plugin_id: str, namespace: str) -> None:
        self.store.revoke(plugin_id, "storage.read", namespace)

    def seed_declared_data(self) -> int:
        inserted = 0
        for bundle in self.registry.discover():
            if not bundle.seed_file.exists():
                continue
            payload = json.loads(bundle.seed_file.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"{bundle.seed_file} must contain a JSON list")
            scoped = self.scoped_store(bundle.manifest.id)
            for item in payload:
                if not isinstance(item, dict):
                    raise ValueError(f"invalid seed item in {bundle.seed_file}")
                inserted += int(
                    scoped.append(
                        str(item["namespace"]),
                        str(item["record_key"]),
                        dict(item["payload"]),
                        observed_at=item.get("observed_at"),
                        source=item.get("source"),
                    )
                )
        return inserted

    def manifest(self, plugin_id: str) -> PluginManifest:
        return self.bundle(plugin_id).manifest
