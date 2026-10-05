"""Data-only discovery contract for trusted, replaceable local shells.

This is not a guest capability, remote API, or automatic activation mechanism.
"""

from __future__ import annotations

from typing import Any, Protocol

from academicos.lifehub.registry import PluginRegistry

CATALOG_API = "lifehub.catalog@1"


class CatalogProvider(Protocol):
    def catalog(self, *, api: str = CATALOG_API, point: str | None = None) -> dict[str, Any]: ...


def build_catalog(
    registry: PluginRegistry, *, api: str = CATALOG_API, point: str | None = None
) -> dict[str, Any]:
    """Return detached JSON metadata; requested permissions never imply grants.

    Managed registries revalidate approved contents during discovery. Local paths
    and stored personal records are deliberately absent from this contract.
    Both sections derive from one discovery result; this is not an atomic
    filesystem snapshot or an authorization token for later execution.
    """
    if api != CATALOG_API:
        raise ValueError(f"unsupported catalog API: {api}")
    bundles = registry.discover()
    return {
        "api": CATALOG_API,
        "packages": [
            {
                "id": bundle.manifest.id,
                "name": bundle.manifest.name,
                "version": bundle.manifest.version,
                "api": bundle.manifest.api,
                "requested_permissions": bundle.manifest.permissions.model_dump(mode="json"),
            }
            for bundle in bundles
        ],
        "extensions": [
            {
                "ref": f"{bundle.manifest.id}:{contribution.id}",
                "plugin_id": bundle.manifest.id,
                **contribution.model_dump(mode="json"),
            }
            for bundle in bundles
            for contribution in bundle.manifest.contributes
            if point is None or contribution.point == point
        ],
    }


def require_contract(contribution, supported: str) -> None:
    """Consumers opt into exact contracts; omitted versions retain legacy behavior."""
    declared = contribution.contract
    if declared is not None and declared != supported:
        raise ValueError(f"unsupported extension contract: {declared}; expected {supported}")
