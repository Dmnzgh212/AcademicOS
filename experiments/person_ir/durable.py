"""SQLite recovery probes for local state and uncertain external-effect intents."""

from dataclasses import asdict
import json
import sqlite3
from threading import RLock

from .model import TraceStep
from .state import CommitReceipt, StateStore


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


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
            self._ledger[identifier] = CommitReceipt(**item)

    def snapshot(self):
        with self._lock:
            self._reload()
            return super().snapshot()

    def commit(self, request, authority, handle, **kwargs):
        with self._lock:
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
