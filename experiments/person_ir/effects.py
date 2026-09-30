"""Host-owned fake effects with conservative, in-memory replay handling."""

from dataclasses import dataclass
from datetime import datetime
import json
import sqlite3
from threading import RLock
from typing import Any

from .authority import AuthorityStore
from .model import EffectRequest, TraceStep, effect_identity
from .policy import EffectPolicy, Evidence
from .runtime import _json_value


class InvalidEffect(ValueError):
    pass


class EffectRejected(Exception):
    """Executor definitely rejected before performing an action."""


class EffectUncertain(Exception):
    """Executor may have performed an action; never retry automatically."""


@dataclass(frozen=True)
class FakeAction:
    effect_id: str
    kind: str
    destination: str
    payload: Any
    external_ref: str


class FakeExecutor:
    """Deterministic host test double. No email, payment, or device I/O."""

    def __init__(self, fail_mode: str | None = None):
        if fail_mode not in (None, "before", "after"):
            raise ValueError("fail_mode must be before, after or None")
        self.fail_mode = fail_mode
        self.actions: list[FakeAction] = []

    def perform(self, request: EffectRequest) -> str:
        if self.fail_mode == "before":
            raise EffectRejected("fake executor rejected before action")
        ref = f"fake:{len(self.actions) + 1}"
        self.actions.append(FakeAction(request.effect_id, request.kind,
                                       request.destination, _json_value(request.payload), ref))
        if self.fail_mode == "after":
            raise EffectUncertain("fake executor lost acknowledgement after action")
        return ref


class IdempotentProviderEmulator:
    """Separate, durable fake provider ledger; never performs external I/O."""

    def __init__(self, path: str, *, interrupt_after: bool = False):
        self._db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self._db.execute("CREATE TABLE IF NOT EXISTS provider_actions "
                         "(effect_id TEXT PRIMARY KEY, request_json TEXT NOT NULL, external_ref TEXT NOT NULL)")
        self.interrupt_after = interrupt_after

    @staticmethod
    def _request_json(request: EffectRequest) -> str:
        return json.dumps([request.kind, request.destination, _json_value(request.payload)],
                          sort_keys=True, separators=(",", ":"))

    def perform(self, request: EffectRequest) -> str:
        encoded = self._request_json(request)
        ref = f"fake-provider:{request.effect_id}"
        with self._db:
            self._db.execute("INSERT OR IGNORE INTO provider_actions VALUES (?, ?, ?)",
                             (request.effect_id, encoded, ref))
            row = self._db.execute(
                "SELECT request_json, external_ref FROM provider_actions WHERE effect_id=?",
                (request.effect_id,)).fetchone()
            if row[0] != encoded:
                raise InvalidEffect("provider effect ID reused with different content")
        if self.interrupt_after:
            raise KeyboardInterrupt("simulated interruption after provider commit")
        return row[1]

    def lookup(self, request: EffectRequest) -> str | None:
        row = self._db.execute(
            "SELECT request_json, external_ref FROM provider_actions WHERE effect_id=?",
            (request.effect_id,)).fetchone()
        if row is None:
            return None
        if row[0] != self._request_json(request):
            raise InvalidEffect("provider record conflicts with effect request")
        return row[1]

    def action_count(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM provider_actions").fetchone()[0]

    def close(self):
        self._db.close()


@dataclass(frozen=True)
class EffectReceipt:
    effect_id: str
    domain: str
    kind: str
    destination: str
    status: str  # succeeded | failed | unknown
    external_ref: str | None
    error: str | None
    authority_ids: tuple[str, ...]
    recorded_at: datetime
    trace: tuple[TraceStep, ...]


@dataclass(frozen=True)
class EffectOutcome:
    receipt: EffectReceipt
    replayed: bool
    checked_at: datetime


def _validated_identity(request: EffectRequest) -> str:
    try:
        payload = _json_value(request.payload)
        if (type(request.producer) is not str or not request.producer.strip() or
                type(request.node_id) is not str or not request.node_id.strip() or
                type(request.intent_id) is not str or not request.intent_id.strip() or
                type(request.sources) is not frozenset or
                any(type(source) is not str for source in request.sources)):
            raise ValueError("invalid effect metadata")
        expected = effect_identity(
            producer=request.producer, node_id=request.node_id,
            intent_id=request.intent_id, kind=request.kind,
            destination=request.destination, payload=payload, label=request.label,
            disclosure_purpose=request.disclosure.purpose if request.disclosure else None,
            sources=request.sources, trace=request.trace)
    except (TypeError, ValueError) as exc:
        raise InvalidEffect("malformed effect request") from exc
    if expected != request.effect_id:
        raise InvalidEffect("effect content changed since creation")
    return expected


class EffectService:
    """Trusted host API. The IR can only produce requests, never call executors."""

    def __init__(self, executors: dict[str, FakeExecutor | IdempotentProviderEmulator], *,
                 policy: EffectPolicy | None = None):
        if type(executors) is not dict or not executors or any(
                type(kind) is not str or type(executor) not in (FakeExecutor, IdempotentProviderEmulator)
                for kind, executor in executors.items()):
            raise ValueError("only explicit host fake executors or provider emulators are supported")
        self._executors = executors.copy()
        if policy is not None and not isinstance(policy, EffectPolicy):
            raise TypeError("host effect policy required")
        self._policy = policy
        self._ledger: dict[tuple[str, str], EffectReceipt] = {}
        self._lock = RLock()

    def receipt(self, domain: str, effect_id: str) -> EffectReceipt | None:
        with self._lock:
            return self._ledger.get((domain, effect_id))

    def execute(self, request: EffectRequest, authority: AuthorityStore, effect_handle: object, *,
                principal: str, domain: str, agent: str,
                disclosure_handle: object | None = None,
                context: str | None = None, now: datetime | None = None,
                evidence: dict[str, Evidence] | None = None) -> EffectOutcome:
        if not isinstance(request, EffectRequest) or not isinstance(authority, AuthorityStore):
            raise TypeError("effect request and trusted authority store required")
        # Live grant check and local ledger/action are serialized with revocation.
        # This does NOT provide atomicity with a real external service or a crash.
        with authority._lock, self._lock:
            check = authority.check_effect_request(
                request, effect_handle, principal=principal, domain=domain, agent=agent,
                disclosure_handle=disclosure_handle, context=context, now=now)
            expected = _validated_identity(request)
            key = (domain, expected)
            previous = self._ledger.get(key)
            if previous is not None:
                return EffectOutcome(previous, True, check.checked_at)
            executor = self._executors.get(request.kind)
            if executor is None:
                raise InvalidEffect("no host executor for effect kind")
            if self._policy is not None:
                self._policy.evaluate(request, evidence, now=check.checked_at)
            try:
                external_ref = executor.perform(request)
                status, error = "succeeded", None
            except EffectRejected as exc:
                external_ref, status, error = None, "failed", str(exc)
            except Exception as exc:
                # Including an unexpected exception: its outcome could be unknown.
                external_ref, status, error = None, "unknown", type(exc).__name__
            receipt = EffectReceipt(expected, domain, request.kind, request.destination,
                                    status, external_ref, error, check.capability_ids,
                                    check.checked_at, request.trace)
            self._ledger[key] = receipt
            return EffectOutcome(receipt, False, check.checked_at)
