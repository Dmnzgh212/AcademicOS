"""Host-owned, in-memory versioned state for the PersonIR commit experiment."""

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any

from .authority import AuthorityError, AuthorityStore
from .model import CommitRequest, TraceStep, proposal_identity
from .runtime import _json_value


class StaleProposal(ValueError):
    pass


class InvalidProposal(ValueError):
    pass


@dataclass(frozen=True)
class StateSnapshot:
    domain: str
    version: int
    values: dict[str, Any]


@dataclass(frozen=True)
class CommitReceipt:
    proposal_id: str
    domain: str
    target: str
    old_version: int
    new_version: int
    applied: bool
    sources: frozenset[str]
    trace: tuple[TraceStep, ...]
    authority_id: str
    authority_ids: tuple[str, ...] = ()  # primary plus co-signers; old receipts may omit


@dataclass(frozen=True)
class CommitOutcome:
    receipt: CommitReceipt
    replayed: bool
    checked_at: datetime
    checked_capability_id: str


class StateStore:
    """Trusted host API; not directly exposed to IR or third-party Python."""

    def __init__(self, domain: str, initial: dict[str, Any] | None = None):
        if type(domain) is not str or not domain.strip():
            raise ValueError("domain required")
        state = {} if initial is None else _json_value(initial)
        if type(state) is not dict:
            raise ValueError("initial state must be an object")
        self.domain = domain
        self._values = state
        self._version = 0
        self._ledger: dict[str, CommitReceipt] = {}
        self._lock = RLock()

    def snapshot(self) -> StateSnapshot:
        """Trusted host read; a future state-view API needs separate read authority."""
        with self._lock:
            return StateSnapshot(self.domain, self._version, _json_value(self._values))

    def commit(self, request: CommitRequest, authority: AuthorityStore, handle: object, *,
               principal: str, agent: str, context: str | None = None,
               now: datetime | None = None,
               additional_grants: tuple[tuple[str, object], ...] = ()) -> CommitOutcome:
        if not isinstance(authority, AuthorityStore) or not isinstance(request, CommitRequest):
            raise TypeError("trusted authority store and commit request required")
        if (type(additional_grants) is not tuple or
                any(type(item) is not tuple or len(item) != 2 or
                    type(item[0]) is not str or not item[0].strip()
                    for item in additional_grants)):
            raise AuthorityError("invalid co-signer grants")
        principals = (principal, *(item[0] for item in additional_grants))
        if len(set(principals)) != len(principals):
            raise AuthorityError("distinct principals required")
        # Lock order is authority -> state. Revocation cannot interleave with the
        # final check and this in-process mutation; no external effect is involved.
        with authority._lock, self._lock:
            check = authority.check_commit_request(request, handle, principal=principal,
                                                   domain=self.domain, agent=agent,
                                                   context=context, now=now)
            co_checks = [authority.check_commit_request(
                request, co_handle, principal=co_principal, domain=self.domain,
                agent=agent, context=context, now=now)
                for co_principal, co_handle in additional_grants]
            checked_ids = (check.capability_ids[0],
                           *(co_check.capability_ids[0] for co_check in co_checks))
            proposal = request.proposal
            try:
                value = _json_value(proposal.value)
                if (type(proposal.target) is not str or not proposal.target.strip() or
                        type(proposal.base_version) is not int or proposal.base_version < 0 or
                        type(proposal.producer) is not str or not proposal.producer.strip() or
                        type(proposal.node_id) is not str or not proposal.node_id.strip() or
                        type(proposal.sources) is not frozenset or
                        any(type(source) is not str for source in proposal.sources)):
                    raise ValueError("invalid proposal metadata")
                expected_id = proposal_identity(producer=proposal.producer,
                                                node_id=proposal.node_id,
                                                target=proposal.target, value=value,
                                                base_version=proposal.base_version,
                                                sources=proposal.sources, trace=proposal.trace)
            except (TypeError, ValueError) as exc:
                raise InvalidProposal("malformed proposal") from exc
            if proposal.proposal_id != expected_id:
                raise InvalidProposal("proposal content changed since creation")
            previous = self._ledger.get(expected_id)
            if previous is not None:
                if len(previous.authority_ids or (previous.authority_id,)) != len(checked_ids):
                    raise AuthorityError("same number of live co-signer grants required for replay")
                return CommitOutcome(previous, True, check.checked_at, check.capability_ids[0])
            if proposal.base_version != self._version:
                raise StaleProposal(f"expected state version {proposal.base_version}, current {self._version}")
            old_version = self._version
            missing = object()
            applied = self._values.get(proposal.target, missing) != value
            if applied:
                self._values[proposal.target] = value
                self._version += 1
            receipt = CommitReceipt(expected_id, self.domain, proposal.target,
                                    old_version, self._version, applied, proposal.sources,
                                    proposal.trace, check.capability_ids[0], checked_ids)
            self._ledger[expected_id] = receipt
            return CommitOutcome(receipt, False, check.checked_at, check.capability_ids[0])
