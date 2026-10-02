"""Host-owned, revocable authority kept outside PersonIR values and graphs."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Callable

from .runtime import Intent


class Capability:
    """Opaque in-process handle. Only the issuing registry accepts its own instance."""

    __slots__ = ("_id",)

    def __init__(self, capability_id: str) -> None:
        self._id = capability_id


@dataclass(frozen=True)
class CapabilityInfo:
    capability_id: str
    principal: str
    domain: str
    operation: str
    resource: str
    scope: str
    issuer: str
    issued_at: datetime
    expires_at: datetime | None
    activation_context: str | None
    revoked: bool = False


def _resource(intent: Intent) -> tuple[str, str]:
    if intent.kind == "commit_request":
        return "state.commit", json.dumps(
            [intent.parameters["namespace"], intent.parameters["key"]], separators=(",", ":")
        )
    if intent.kind == "effect_request":
        return "effect.dispatch", json.dumps(
            [intent.parameters["kind"], intent.parameters["destination"]], separators=(",", ":")
        )
    raise PermissionError("only commit and effect requests require this authority")


class AuthorityRegistry:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._entries: dict[str, tuple[Capability, CapabilityInfo]] = {}

    def issue(
        self,
        *,
        principal: str,
        domain: str,
        operation: str,
        resource: str,
        issuer: str,
        expires_at: datetime | None = None,
        activation_context: str | None = None,
    ) -> Capability:
        """Trusted host entry point; an IR graph has no instruction to call this."""
        if not all(
            type(value) is str and value
            for value in (principal, domain, operation, resource, issuer)
        ):
            raise ValueError("authority fields must be nonempty strings")
        now = self._clock()
        if now.tzinfo is None or (expires_at is not None and expires_at.tzinfo is None):
            raise ValueError("authority times must be timezone-aware")
        if expires_at is not None and expires_at <= now:
            raise ValueError("capability would already be expired")
        if activation_context is not None and (
            type(activation_context) is not str or not activation_context
        ):
            raise ValueError("activation context must be a nonempty string")
        capability_id = secrets.token_urlsafe(24)
        handle = Capability(capability_id)
        info = CapabilityInfo(
            capability_id,
            principal,
            domain,
            operation,
            resource,
            "exact",
            issuer,
            now,
            expires_at,
            activation_context,
        )
        self._entries[capability_id] = (handle, info)
        return handle

    def inspect(self, handle: Capability) -> CapabilityInfo:
        if not isinstance(handle, Capability):
            raise PermissionError("capability handle required")
        entry = self._entries.get(handle._id)
        if entry is None or entry[0] is not handle:
            raise PermissionError("capability was not issued by this registry")
        return entry[1]

    def issue_for_intent(
        self,
        intent: Intent,
        *,
        principal: str,
        domain: str,
        issuer: str,
        expires_at: datetime | None = None,
        activation_context: str | None = None,
    ) -> Capability:
        """Trusted review path; bind an exact operation and resource to one intent."""
        operation, resource = _resource(intent)
        return self.issue(
            principal=principal,
            domain=domain,
            operation=operation,
            resource=resource,
            issuer=issuer,
            expires_at=expires_at,
            activation_context=activation_context,
        )

    def revoke(self, handle: Capability) -> None:
        info = self.inspect(handle)
        self._entries[info.capability_id] = (handle, replace(info, revoked=True))

    def require(
        self,
        handle: Capability,
        *,
        principal: str,
        domain: str,
        operation: str,
        resource: str,
        context: str | None = None,
    ) -> CapabilityInfo:
        """Re-evaluate on use; an earlier successful check is not a durable grant."""
        info = self.inspect(handle)
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("authority clock must be timezone-aware")
        if info.revoked or (info.expires_at is not None and now >= info.expires_at):
            raise PermissionError("capability is revoked or expired")
        if (
            info.principal != principal
            or info.domain != domain
            or info.operation != operation
            or info.resource != resource
            or (info.activation_context is not None and info.activation_context != context)
        ):
            raise PermissionError("capability scope does not match request")
        return info

    def require_intent(
        self,
        handle: Capability,
        intent: Intent,
        *,
        principal: str,
        domain: str,
        context: str | None = None,
    ) -> CapabilityInfo:
        operation, resource = _resource(intent)
        return self.require(
            handle,
            principal=principal,
            domain=domain,
            operation=operation,
            resource=resource,
            context=context,
        )
