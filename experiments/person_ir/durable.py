"""SQLite recovery probes for local state and uncertain external-effect intents."""

from dataclasses import asdict, replace
from datetime import datetime
import json
import sqlite3
from threading import RLock

from .authority import AuthorityError, AuthorityStore, Grant, _CapabilityHandle
from .effects import (EffectOutcome, EffectReceipt, EffectRejected, EffectService,
                      EffectUncertain, InvalidEffect, _validated_identity)
from .model import EffectRequest
from .model import TraceStep
from .policy import EffectPolicy, Evidence
from .state import CommitReceipt, StateStore


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class DurableAuthorityStore(AuthorityStore):
    """Host-only SQLite grant registry with fresh object handles on restart.

    The host must authenticate its own startup/session before distributing any
    recovered handles. A grant ID or serialized description is never accepted
    directly by check_* APIs.
    """

    def __init__(self, path: str):
        super().__init__()
        self._db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS authority_grants "
            "(capability_id TEXT PRIMARY KEY, grant_json TEXT NOT NULL, revoked INTEGER NOT NULL)")
        for identifier, encoded, revoked in self._db.execute(
                "SELECT capability_id, grant_json, revoked FROM authority_grants"):
            fields = json.loads(encoded)
            fields["issued_at"] = datetime.fromisoformat(fields["issued_at"])
            fields["expires_at"] = (datetime.fromisoformat(fields["expires_at"])
                                    if fields["expires_at"] else None)
            grant = Grant(**(fields | {"revoked": bool(revoked)}))
            handle = _CapabilityHandle()
            self._handles[handle] = identifier
            self._grants[identifier] = grant

    def host_handles(self) -> dict[str, object]:
        """Trusted startup handoff only; never expose this map to extensions."""
        with self._lock:
            return {identifier: handle for handle, identifier in self._handles.items()}

    def issue(self, **kwargs) -> object:
        with self._lock:
            handle = super().issue(**kwargs)
            grant = self.describe(handle)
            encoded = asdict(grant)
            encoded["issued_at"] = grant.issued_at.isoformat()
            encoded["expires_at"] = grant.expires_at.isoformat() if grant.expires_at else None
            try:
                self._db.execute("INSERT INTO authority_grants VALUES (?, ?, 0)",
                                 (grant.capability_id, _dump(encoded)))
            except BaseException:
                self._handles.pop(handle)
                self._grants.pop(grant.capability_id)
                raise
            return handle

    def revoke(self, capability_id: str) -> None:
        with self._lock:
            if capability_id not in self._grants:
                raise AuthorityError("unknown capability id")
            self._db.execute("UPDATE authority_grants SET revoked=1 WHERE capability_id=?",
                             (capability_id,))
            super().revoke(capability_id)

    def _check(self, handle, **kwargs) -> str:
        grant = self.describe(handle)
        row = self._db.execute(
            "SELECT revoked FROM authority_grants WHERE capability_id=?",
            (grant.capability_id,)).fetchone()
        if row is None:
            raise AuthorityError("grant missing from durable registry")
        self._grants[grant.capability_id] = replace(grant, revoked=bool(row[0]))
        return super()._check(handle, **kwargs)

    def close(self):
        self._db.close()


class DurableStateStore(StateStore):
    """A single-domain SQLite-backed version and receipt ledger."""

    def __init__(self, path: str, domain: str, initial: dict | None = None):
        super().__init__(domain, initial)
        self._db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self._db.execute("CREATE TABLE IF NOT EXISTS state (domain TEXT PRIMARY KEY, version INTEGER NOT NULL, vals TEXT NOT NULL)")
        self._db.execute("CREATE TABLE IF NOT EXISTS commits (domain TEXT NOT NULL, proposal_id TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(domain, proposal_id))")
        self._db.execute("INSERT OR IGNORE INTO state VALUES (?, 0, ?)", (domain, _dump(self._values)))
        self._reload()

    def _reload(self):
        self._version, vals = self._db.execute(
            "SELECT version, vals FROM state WHERE domain=?", (self.domain,)).fetchone()
        self._values = json.loads(vals)
        self._ledger = {}
        for identifier, encoded in self._db.execute(
                "SELECT proposal_id, receipt FROM commits WHERE domain=?", (self.domain,)):
            item = json.loads(encoded)
            item["sources"] = frozenset(item["sources"])
            item["trace"] = tuple(TraceStep(**(step | {"input_ids": tuple(step["input_ids"])}))
                                  for step in item["trace"])
            if "authority_ids" in item:
                item["authority_ids"] = tuple(item["authority_ids"])
            self._ledger[identifier] = CommitReceipt(**item)

    def snapshot(self):
        with self._lock:
            self._reload()
            return super().snapshot()

    def commit(self, request, authority, handle, **kwargs):
        if not isinstance(authority, AuthorityStore):
            raise TypeError("trusted authority store required")
        # Preserve the authority -> state -> SQLite lock order used by the
        # in-memory store, including when grants share this SQLite database.
        with authority._lock, self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._reload()
                outcome = super().commit(request, authority, handle, **kwargs)
                receipt = outcome.receipt
                self._db.execute("UPDATE state SET version=?, vals=? WHERE domain=?",
                                 (self._version, _dump(self._values), self.domain))
                encoded = asdict(receipt)
                encoded["sources"] = sorted(receipt.sources)
                self._db.execute("INSERT OR IGNORE INTO commits VALUES (?, ?, ?)",
                                 (self.domain, receipt.proposal_id, _dump(encoded)))
                self._db.execute("COMMIT")
                return outcome
            except BaseException:
                self._db.execute("ROLLBACK")
                self._reload()
                raise

    def close(self):
        self._db.close()


class DurableEffectJournal:
    """Persist intent before I/O. An unfinished intent is unknown after restart."""

    def __init__(self, path: str):
        self._db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self._lock = RLock()
        self._db.execute("CREATE TABLE IF NOT EXISTS effect_intents (domain TEXT NOT NULL, effect_id TEXT NOT NULL, status TEXT NOT NULL, receipt TEXT, PRIMARY KEY(domain, effect_id))")

    def begin(self, domain: str, effect_id: str) -> bool:
        """Return true only for a new intent; never automatically retry an old one."""
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT OR IGNORE INTO effect_intents VALUES (?, ?, 'unknown', NULL)",
                (domain, effect_id))
            return cursor.rowcount == 1

    def finish(self, domain: str, effect_id: str, receipt: dict):
        if receipt.get("status") not in {"succeeded", "failed", "unknown"}:
            raise ValueError("invalid terminal effect status")
        with self._lock, self._db:
            cursor = self._db.execute(
                "UPDATE effect_intents SET status=?, receipt=? WHERE domain=? AND effect_id=? AND receipt IS NULL",
                (receipt["status"], _dump(receipt), domain, effect_id))
            if cursor.rowcount != 1:
                raise ValueError("missing or already finished intent")

    def lookup(self, domain: str, effect_id: str):
        with self._lock:
            row = self._db.execute(
                "SELECT status, receipt FROM effect_intents WHERE domain=? AND effect_id=?",
                (domain, effect_id)).fetchone()
            return None if row is None else (row[0], json.loads(row[1]) if row[1] else None)

    def close(self):
        self._db.close()


def _encoded_effect(receipt: EffectReceipt) -> dict:
    result = asdict(receipt)
    result["recorded_at"] = receipt.recorded_at.isoformat()
    return result


def _restored_effect(data: dict) -> EffectReceipt:
    try:
        result = data.copy()
        result["recorded_at"] = datetime.fromisoformat(result["recorded_at"])
        result["authority_ids"] = tuple(result["authority_ids"])
        result["trace"] = tuple(TraceStep(**(step | {"input_ids": tuple(step["input_ids"])}))
                                for step in result["trace"])
        return EffectReceipt(**result)
    except (KeyError, TypeError, ValueError) as exc:
        raise EffectUncertain("journal entry lacks a complete effect receipt") from exc


class DurableEffectService(EffectService):
    """Fake effects with a durable intent-before-action boundary.

    A pending intent may already have acted. Replays raise EffectUncertain until
    reconciliation, while completed receipts replay after another live grant check.
    """

    def __init__(self, path: str, executors: dict, *, policy: EffectPolicy | None = None):
        super().__init__(executors, policy=policy)
        self._journal = DurableEffectJournal(path)

    def receipt(self, domain: str, effect_id: str) -> EffectReceipt | None:
        entry = self._journal.lookup(domain, effect_id)
        return _restored_effect(entry[1]) if entry and entry[1] is not None else None

    def execute(self, request: EffectRequest, authority: AuthorityStore, effect_handle: object, *,
                principal: str, domain: str, agent: str,
                disclosure_handle: object | None = None,
                context: str | None = None, now: datetime | None = None,
                evidence: dict[str, Evidence] | None = None) -> EffectOutcome:
        if not isinstance(request, EffectRequest) or not isinstance(authority, AuthorityStore):
            raise TypeError("effect request and trusted authority store required")
        with authority._lock, self._lock:
            check = authority.check_effect_request(
                request, effect_handle, principal=principal, domain=domain, agent=agent,
                disclosure_handle=disclosure_handle, context=context, now=now)
            identifier = _validated_identity(request)
            executor = self._executors.get(request.kind)
            if executor is None:
                raise InvalidEffect("no host executor for effect kind")
            previous = self._journal.lookup(domain, identifier)
            if previous is not None:
                if previous[1] is None:
                    raise EffectUncertain("pending effect outcome unknown; reconcile before retry")
                return EffectOutcome(_restored_effect(previous[1]), True, check.checked_at)
            if self._policy is not None:
                self._policy.evaluate(request, evidence, now=check.checked_at)
            if not self._journal.begin(domain, identifier):
                # A competing host process may have inserted after lookup.
                previous = self._journal.lookup(domain, identifier)
                if previous is None or previous[1] is None:
                    raise EffectUncertain("pending effect outcome unknown; reconcile before retry")
                return EffectOutcome(_restored_effect(previous[1]), True, check.checked_at)
            # The committed journal row exists before the fake external action.
            try:
                external_ref = executor.perform(request)
                status, error = "succeeded", None
            except EffectRejected as exc:
                external_ref, status, error = None, "failed", str(exc)
            except Exception as exc:
                external_ref, status, error = None, "unknown", type(exc).__name__
            receipt = EffectReceipt(identifier, domain, request.kind, request.destination,
                                    status, external_ref, error, check.capability_ids,
                                    check.checked_at, request.trace)
            try:
                self._journal.finish(domain, identifier, _encoded_effect(receipt))
            except Exception as exc:
                raise EffectUncertain("effect outcome could not be durably recorded") from exc
            return EffectOutcome(receipt, False, check.checked_at)

    def close(self):
        self._journal.close()
