from __future__ import annotations

import json
import hashlib
from pathlib import Path

from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.effects import EffectService
from academicos.lifehub.network import EgressGateway
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.proposals import ProposalService
from academicos.lifehub.protocol import CATALOG_API, build_catalog, require_contract
from academicos.lifehub.registry import PluginBundle, PluginRegistry, RegisteredExtension
from academicos.lifehub.service_runtime import SERVICE_JSON_CONTRACT, run_json_service
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
        self.proposals = ProposalService(self.store)
        self.effects = EffectService(self.store)
        self.last_proposal_ids: list[int] = []
        self.last_effect_ids: list[int] = []
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

    def catalog(self, *, api: str = CATALOG_API, point: str | None = None) -> dict:
        """Versioned metadata discovery for trusted local shells; grants no authority."""
        return build_catalog(self.registry, api=api, point=point)

    def scoped_store(self, plugin_id: str):  # noqa: ANN201
        return self.store.scoped(
            self.bundle(plugin_id).manifest, verify=lambda: self.bundle(plugin_id)
        )

    def egress(self, plugin_id: str) -> EgressGateway:
        return EgressGateway(
            self.store, self.bundle(plugin_id).manifest, verify=lambda: self.bundle(plugin_id)
        )

    def _service_binding(self, caller_id: str, ref: str, contract: str) -> str:
        """Trusted host activation; identities must never come from untrusted payloads."""
        if not self.packages.is_managed():
            raise PermissionError("service activation requires approved installed packages")
        caller = self.bundle(caller_id)
        if ref not in caller.manifest.permissions.service_call:
            raise PermissionError("caller did not request this exact service")
        extension = self.extension(ref)
        if extension.contribution.point != "lifehub.service":
            raise ValueError("target is not a service contribution")
        if extension.contribution.contract != contract:
            raise ValueError("service contract mismatch")
        if contract not in ("lifehub.core-wasm@1", SERVICE_JSON_CONTRACT):
            raise ValueError("unsupported service contract")
        if extension.contribution.entrypoint != "lifehub.wasm":
            raise ValueError("service activation supports core-Wasm only")
        provider = self.bundle(extension.plugin_id)
        digests = []
        for bundle in (caller, provider):
            self.packages.verify(bundle.root, bundle.manifest)
            row = self.store.conn.execute(
                "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
                (bundle.manifest.id,),
            ).fetchone()
            if row is None:
                raise PermissionError("service package approval missing")
            digests.append(row["content_hash"])
        return json.dumps([ref, contract, *digests], separators=(",", ":"))

    def review_service(self, caller_id: str, ref: str, contract: str) -> dict:
        binding = self._service_binding(caller_id, ref, contract)
        parts = json.loads(binding)
        provider_id = self.extension(ref).plugin_id
        row = self.store.conn.execute(
            "SELECT 1 FROM lifehub_permission_grants "
            "WHERE plugin_id=? AND capability=? AND resource=?",
            (caller_id, "service.activate", binding),
        ).fetchone()
        return {
            "api": "lifehub.service-review@1",
            "caller": caller_id,
            "provider": provider_id,
            "ref": ref,
            "contract": contract,
            "caller_digest": parts[2],
            "provider_digest": parts[3],
            "provider_requested_permissions": self.manifest(provider_id).permissions.model_dump(
                mode="json"
            ),
            "granted": row is not None,
            "approval_digest": hashlib.sha256(
                json.dumps([caller_id, binding], separators=(",", ":")).encode()
            ).hexdigest(),
        }

    def grant_service(
        self, caller_id: str, ref: str, contract: str, *, approved_digest: str | None = None
    ) -> None:
        binding = self._service_binding(caller_id, ref, contract)
        if approved_digest is not None:
            review = self.review_service(caller_id, ref, contract)
            if review["approval_digest"] != approved_digest:
                raise PermissionError("service review changed; review again before granting")
        self.store.grant(caller_id, "service.activate", binding)

    def revoke_service(self, caller_id: str, ref: str, contract: str) -> None:
        # Revocation works even if packages have changed or disappeared.
        for grant in self.store.grants(caller_id):
            if grant["capability"] == "service.activate":
                parts = json.loads(grant["resource"])
                if parts[:2] == [ref, contract]:
                    self.store.revoke(caller_id, "service.activate", grant["resource"])

    def activate_service(self, caller_id: str, ref: str, contract: str) -> int:
        if contract != "lifehub.core-wasm@1":
            raise ValueError("activation requires core-Wasm contract")
        binding = self._service_binding(caller_id, ref, contract)
        row = self.store.conn.execute(
            "SELECT 1 FROM lifehub_permission_grants "
            "WHERE plugin_id=? AND capability=? AND resource=?",
            (caller_id, "service.activate", binding),
        ).fetchone()
        if row is None:
            raise PermissionError("service activation is not granted for these package snapshots")
        return self.run_wasm(ref)

    def call_service(self, caller_id: str, ref: str, request):
        """Trusted-host JSON call; no ambient provider capabilities or guest identity input."""
        contract = SERVICE_JSON_CONTRACT
        binding = self._service_binding(caller_id, ref, contract)
        row = self.store.conn.execute(
            "SELECT 1 FROM lifehub_permission_grants "
            "WHERE plugin_id=? AND capability=? AND resource=?",
            (caller_id, "service.activate", binding),
        ).fetchone()
        if row is None:
            raise PermissionError("service activation is not granted for these package snapshots")
        extension = self.extension(ref)
        bundle = self.bundle(extension.plugin_id)
        files = self.packages.approved_files(bundle.root, bundle.manifest)
        module_name = extension.contribution.config.get("module")
        if not isinstance(module_name, str) or not module_name.endswith(".wasm"):
            raise ValueError("service needs a .wasm module path")
        if module_name not in files:
            raise ValueError("service module is not in approved package")
        output = run_json_service(files[module_name], request)
        if self._service_binding(caller_id, ref, contract) != binding:
            raise PermissionError("service package snapshots changed during execution")
        row = self.store.conn.execute(
            "SELECT 1 FROM lifehub_permission_grants "
            "WHERE plugin_id=? AND capability=? AND resource=?",
            (caller_id, "service.activate", binding),
        ).fetchone()
        if row is None:
            raise PermissionError("service grant revoked during execution")
        return output

    def run_wasm(self, ref: str) -> int:
        """Run approved WebAssembly and persist proposals only after successful return."""
        extension = self.extension(ref)
        require_contract(extension.contribution, "lifehub.core-wasm@1")
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
        runner = WasmRunner(
            self.scoped_store(extension.plugin_id),
            bundle.manifest,
            self.effects,
            service_call=lambda target, request: self.call_service(
                bundle.manifest.id, target, request
            ),
        )
        self.last_proposal_ids = []
        self.last_effect_ids = []
        result = runner.run(files[module_name])
        approved = self.store.conn.execute(
            "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
            (bundle.manifest.id,),
        ).fetchone()
        if approved is None:
            raise PermissionError("package approval was revoked during execution")
        self.packages.verify(bundle.root, bundle.manifest)
        conn = self.store.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            proposal_ids = self.proposals.submit(
                bundle.manifest.id, approved["content_hash"], ref, runner.proposals
            )
            effect_ids = self.effects.submit(
                bundle.manifest, approved["content_hash"], ref, runner.effect_requests
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        self.last_proposal_ids = proposal_ids
        self.last_effect_ids = effect_ids
        return result

    def approve_effect(self, request_id: int) -> None:
        request = self.effects.get(request_id)
        bundle = self.bundle(request["plugin_id"])
        approved = self.store.conn.execute(
            "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
            (bundle.manifest.id,),
        ).fetchone()
        if approved is None:
            raise PermissionError("package is no longer approved")
        self.effects.approve(request_id, bundle.manifest, approved["content_hash"])

    def dispatch_effect(self, request_id: int) -> str:
        request = self.effects.get(request_id)
        bundle = self.bundle(request["plugin_id"])
        approved = self.store.conn.execute(
            "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
            (bundle.manifest.id,),
        ).fetchone()
        if approved is None:
            raise PermissionError("package is no longer approved")
        return self.effects.dispatch(request_id, bundle.manifest, approved["content_hash"])

    def approve_proposal(self, proposal_id: int) -> str:
        proposal = self.proposals.get(proposal_id)
        bundle = self.bundle(proposal["plugin_id"])
        approved = self.store.conn.execute(
            "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
            (bundle.manifest.id,),
        ).fetchone()
        if approved is None:
            raise PermissionError("package is no longer approved")
        return self.proposals.approve(proposal_id, bundle.manifest, approved["content_hash"])

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
