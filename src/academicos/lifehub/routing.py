"""Engine-level interface resolution bound to explicit package authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from academicos.lifehub.kernel import LifeHub

ROUTE_CAPABILITY = "component.interface"


@dataclass(frozen=True)
class InterfaceRoute:
    consumer_ref: str
    interface: str
    provider_ref: str
    consumer_digest: str
    provider_digest: str


class InterfaceRouter:
    """Resolve component requirements only through explicit snapshot-bound grants."""

    def __init__(
        self,
        kernel: LifeHub,
        component_lookup: Callable[[str], Any],
    ) -> None:
        self.kernel = kernel
        self._component_lookup = component_lookup

    def review(self, consumer_ref: str, interface: str, provider_ref: str) -> dict[str, Any]:
        route, binding = self._binding(consumer_ref, interface, provider_ref)
        granted = self._is_granted(route.consumer_ref, binding)
        return {
            "api": "lifehub.interface-route-review@1",
            "consumer": route.consumer_ref,
            "interface": route.interface,
            "provider": route.provider_ref,
            "consumer_digest": route.consumer_digest,
            "provider_digest": route.provider_digest,
            "granted": granted,
            "approval_digest": self._approval_digest(route.consumer_ref, binding),
        }

    def grant(
        self,
        consumer_ref: str,
        interface: str,
        provider_ref: str,
        *,
        approved_digest: str,
    ) -> InterfaceRoute:
        route, binding = self._binding(consumer_ref, interface, provider_ref)
        if self._approval_digest(route.consumer_ref, binding) != approved_digest:
            raise PermissionError("interface route review changed; review again before granting")
        self.kernel.store.grant(
            route.consumer_ref.partition(":")[0],
            ROUTE_CAPABILITY,
            binding,
        )
        return route

    def revoke(
        self,
        consumer_ref: str,
        interface: str,
        provider_ref: str | None = None,
    ) -> int:
        """Revoke matching routes even if provider packages changed or disappeared."""
        consumer_plugin = _plugin_id(consumer_ref)
        revoked = 0
        for grant in self.kernel.store.grants(consumer_plugin):
            if grant["capability"] != ROUTE_CAPABILITY:
                continue
            parts = _decode_binding(grant["resource"])
            if parts[0] != consumer_ref or parts[1] != interface:
                continue
            if provider_ref is not None and parts[2] != provider_ref:
                continue
            self.kernel.store.revoke(
                consumer_plugin,
                ROUTE_CAPABILITY,
                grant["resource"],
            )
            revoked += 1
        return revoked

    def resolve(self, consumer_ref: str, interface: str) -> InterfaceRoute:
        consumer, consumer_digest = self._snapshot(consumer_ref)
        if interface not in consumer.requires:
            raise PermissionError(
                f"component {consumer_ref} did not declare required interface {interface!r}"
            )

        matches: list[InterfaceRoute] = []
        for grant in self.kernel.store.grants(consumer.plugin_id):
            if grant["capability"] != ROUTE_CAPABILITY:
                continue
            parts = _decode_binding(grant["resource"])
            if parts[0] != consumer_ref or parts[1] != interface:
                continue
            provider_ref = parts[2]
            try:
                provider, provider_digest = self._snapshot(provider_ref)
            except KeyError:
                continue
            if interface not in provider.provides:
                continue
            current = InterfaceRoute(
                consumer_ref=consumer_ref,
                interface=interface,
                provider_ref=provider_ref,
                consumer_digest=consumer_digest,
                provider_digest=provider_digest,
            )
            if _encode_binding(current) == grant["resource"]:
                matches.append(current)

        if not matches:
            raise PermissionError(
                f"no granted provider for {consumer_ref} required interface {interface!r}"
            )
        if len(matches) != 1:
            raise PermissionError(
                f"multiple granted providers for {consumer_ref} required interface {interface!r}"
            )
        return matches[0]

    def _binding(
        self, consumer_ref: str, interface: str, provider_ref: str
    ) -> tuple[InterfaceRoute, str]:
        consumer, consumer_digest = self._snapshot(consumer_ref)
        provider, provider_digest = self._snapshot(provider_ref)
        if interface not in consumer.requires:
            raise PermissionError(
                f"component {consumer_ref} did not declare required interface {interface!r}"
            )
        if interface not in provider.provides:
            raise PermissionError(
                f"component {provider_ref} does not provide interface {interface!r}"
            )
        route = InterfaceRoute(
            consumer_ref=consumer_ref,
            interface=interface,
            provider_ref=provider_ref,
            consumer_digest=consumer_digest,
            provider_digest=provider_digest,
        )
        return route, _encode_binding(route)

    def _snapshot(self, ref: str) -> tuple[Any, str]:
        if not self.kernel.packages.is_managed():
            raise PermissionError("interface routing requires approved installed packages")
        component = self._component_lookup(ref)
        bundle = self.kernel.bundle(component.plugin_id)
        self.kernel.packages.verify(bundle.root, bundle.manifest)
        row = self.kernel.store.conn.execute(
            "SELECT content_hash FROM lifehub_installed_packages WHERE plugin_id=?",
            (component.plugin_id,),
        ).fetchone()
        if row is None:
            raise PermissionError(f"package approval missing for component {ref}")
        return component, row["content_hash"]

    def _is_granted(self, consumer_ref: str, binding: str) -> bool:
        consumer_plugin = _plugin_id(consumer_ref)
        row = self.kernel.store.conn.execute(
            """
            SELECT 1 FROM lifehub_permission_grants
            WHERE plugin_id=? AND capability=? AND resource=?
            """,
            (consumer_plugin, ROUTE_CAPABILITY, binding),
        ).fetchone()
        return row is not None

    @staticmethod
    def _approval_digest(consumer_ref: str, binding: str) -> str:
        return hashlib.sha256(
            json.dumps([consumer_ref, binding], separators=(",", ":")).encode()
        ).hexdigest()


def _encode_binding(route: InterfaceRoute) -> str:
    return json.dumps(
        [
            route.consumer_ref,
            route.interface,
            route.provider_ref,
            route.consumer_digest,
            route.provider_digest,
        ],
        separators=(",", ":"),
    )


def _decode_binding(resource: str) -> list[str]:
    try:
        parts = json.loads(resource)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid stored interface route binding") from exc
    if (
        not isinstance(parts, list)
        or len(parts) != 5
        or any(not isinstance(item, str) for item in parts)
    ):
        raise ValueError("invalid stored interface route binding")
    return parts


def _plugin_id(ref: str) -> str:
    plugin_id, separator, component_id = ref.partition(":")
    if not separator or not plugin_id or not component_id:
        raise ValueError(f"invalid component ref: {ref}")
    return plugin_id
