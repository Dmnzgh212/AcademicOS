"""Host-owned, in-memory capability registry for PersonIR slice 2.

Capability IDs and serialized grant descriptions are not bearer tokens. Only a
handle issued by this registry can authorize a request, and checks are live.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import secrets

from .model import CommitRequest, DisclosureRequest, EffectRequest


class AuthorityError(PermissionError):
    pass


class _CapabilityHandle:
    """Identity-bearing object intentionally excluded from JSON and IR values."""

    __slots__ = ()


@dataclass(frozen=True)
class Grant:
    capability_id: str
    principal: str
    domain: str
    agent: str
    operation: str
    resource: str
    issuer: str
    issued_at: datetime
    expires_at: datetime | None = None
    activation_context: str | None = None
    purpose: str | None = None
    revoked: bool = False


@dataclass(frozen=True)
class CheckResult:
    """Audit metadata for one live check; never a durable permission to execute."""

    capability_ids: tuple[str, ...]
    checked_at: datetime


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("a timezone-aware datetime is required")
    return value.astimezone(timezone.utc)


class AuthorityStore:
    """Trusted host API. Never expose this store or issue() to untrusted code."""

    def __init__(self):
        self._handles: dict[_CapabilityHandle, str] = {}
        self._grants: dict[str, Grant] = {}

    def issue(self, *, principal: str, domain: str, agent: str, operation: str,
              resource: str, issuer: str, issued_at: datetime,
              expires_at: datetime | None = None, activation_context: str | None = None,
              purpose: str | None = None) -> object:
        for value in (principal, domain, agent, operation, resource, issuer):
            if type(value) is not str or not value.strip():
                raise ValueError("grant identity, operation, resource and issuer are required")
        if operation == "disclose":
            if type(purpose) is not str or not purpose.strip():
                raise ValueError("disclosure grants require a purpose")
        elif purpose is not None:
            raise ValueError("purpose is only valid for disclosure grants")
        if activation_context is not None and (type(activation_context) is not str or not activation_context.strip()):
            raise ValueError("invalid activation context")
        issued_at = _time(issued_at)
        expires_at = _time(expires_at) if expires_at is not None else None
        if expires_at is not None and expires_at <= issued_at:
            raise ValueError("expiration must follow issuance")
        identifier = secrets.token_hex(16)
        handle = _CapabilityHandle()
        self._handles[handle] = identifier
        self._grants[identifier] = Grant(identifier, principal, domain, agent,
                                         operation, resource, issuer, issued_at,
                                         expires_at, activation_context, purpose)
        return handle

    def describe(self, handle: object) -> Grant:
        """Return non-authorizing metadata; its capability_id is not a credential."""
        if type(handle) is not _CapabilityHandle or handle not in self._handles:
            raise AuthorityError("unknown capability handle")
        return self._grants[self._handles[handle]]

    def revoke(self, capability_id: str) -> None:
        if capability_id not in self._grants:
            raise AuthorityError("unknown capability id")
        self._grants[capability_id] = replace(self._grants[capability_id], revoked=True)

    def _check(self, handle: object, *, principal: str, domain: str, agent: str,
               operation: str, resource: str, purpose: str | None,
               context: str | None, now: datetime) -> str:
        grant = self.describe(handle)
        if grant.revoked:
            raise AuthorityError("capability revoked")
        if now < grant.issued_at or (grant.expires_at is not None and now >= grant.expires_at):
            raise AuthorityError("capability outside validity period")
        if (grant.principal, grant.domain, grant.agent, grant.operation, grant.resource, grant.purpose) != (
                principal, domain, agent, operation, resource, purpose):
            raise AuthorityError("capability scope mismatch")
        if grant.activation_context is not None and grant.activation_context != context:
            raise AuthorityError("activation context mismatch")
        return grant.capability_id

    def check_commit_request(self, request: CommitRequest, handle: object, *,
                             principal: str, domain: str, agent: str,
                             context: str | None = None, now: datetime | None = None) -> CheckResult:
        if not isinstance(request, CommitRequest):
            raise TypeError("commit request required")
        checked = _time(now or datetime.now(timezone.utc))
        identifier = self._check(handle, principal=principal, domain=domain,
                                 agent=agent, operation="commit", resource=request.proposal.target,
                                 purpose=None, context=context, now=checked)
        return CheckResult((identifier,), checked)

    def check_disclosure_request(self, request: DisclosureRequest, handle: object, *,
                                 principal: str, domain: str, agent: str,
                                 context: str | None = None,
                                 now: datetime | None = None) -> CheckResult:
        if not isinstance(request, DisclosureRequest):
            raise TypeError("disclosure request required")
        checked = _time(now or datetime.now(timezone.utc))
        identifier = self._check(handle, principal=principal, domain=domain,
                                 agent=agent, operation="disclose", resource=request.destination,
                                 purpose=request.purpose, context=context, now=checked)
        return CheckResult((identifier,), checked)

    def check_effect_request(self, request: EffectRequest, effect_handle: object, *,
                             principal: str, domain: str, agent: str,
                             disclosure_handle: object | None = None,
                             context: str | None = None,
                             now: datetime | None = None) -> CheckResult:
        if not isinstance(request, EffectRequest):
            raise TypeError("effect request required")
        if request.label not in {"public", "protected"} or (request.label == "protected" and request.disclosure is None):
            raise AuthorityError("protected effect requires disclosure")
        checked = _time(now or datetime.now(timezone.utc))
        identifiers = [self._check(effect_handle, principal=principal, domain=domain,
                                   agent=agent, operation=f"effect:{request.kind}",
                                   resource=request.destination, purpose=None,
                                   context=context, now=checked)]
        if request.disclosure is not None:
            if (request.disclosure.destination != request.destination or
                    request.disclosure.value != request.payload):
                raise AuthorityError("effect and disclosure mismatch")
            identifiers.append(self._check(disclosure_handle, principal=principal, domain=domain,
                                           agent=agent, operation="disclose",
                                           resource=request.disclosure.destination,
                                           purpose=request.disclosure.purpose,
                                           context=context, now=checked))
        return CheckResult(tuple(identifiers), checked)
