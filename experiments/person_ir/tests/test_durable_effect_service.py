import tempfile
import unittest
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from experiments.person_ir import AuthorityError, AuthorityStore, FakeExecutor, InvalidEffect
from experiments.person_ir.durable import DurableEffectJournal, DurableEffectService, _encoded_effect
from experiments.person_ir.effects import EffectReceipt, EffectUncertain, IdempotentProviderEmulator
from experiments.person_ir.examples import email


NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)
DEST = "alice@example.com"
ACTOR = {"principal": "person:1", "domain": "personal:1", "agent": "mail@1"}


class DurableEffectServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "effects.sqlite")
        self.provider_path = str(Path(self.temp.name) / "provider.sqlite")
        self.authority = AuthorityStore()
        args = ACTOR | {"resource": DEST, "issuer": "person:1", "issued_at": NOW}
        self.send = self.authority.issue(**(args | {"operation": "effect:email"}))
        self.disclose = self.authority.issue(**(args | {
            "operation": "disclose", "purpose": "send requested email"}))
        self.item = email.request(DEST, intent_id="one")

    def execute(self, service, item=None, **changes):
        kwargs = dict(authority=self.authority, effect_handle=self.send,
                      disclosure_handle=self.disclose, now=NOW, **ACTOR)
        kwargs.update(changes)
        return service.execute(item or self.item, **kwargs)

    def test_completed_receipt_survives_restart_and_rechecks_live_grant(self):
        executor = FakeExecutor()
        service = DurableEffectService(self.path, {"email": executor})
        first = self.execute(service)
        self.assertEqual(first.receipt.status, "succeeded")
        service.close()
        restarted = DurableEffectService(self.path, {"email": FakeExecutor()})
        replay = self.execute(restarted)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, first.receipt)
        self.assertEqual(restarted._executors["email"].actions, [])
        self.authority.revoke(self.authority.describe(self.send).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.execute(restarted)
        restarted.close()

    def test_pending_intent_blocks_action_after_restart(self):
        journal = DurableEffectJournal(self.path)
        self.assertTrue(journal.begin(ACTOR["domain"], self.item.effect_id))
        journal.close()  # Crash could occur before or after external action.
        executor = FakeExecutor()
        service = DurableEffectService(self.path, {"email": executor})
        with self.assertRaisesRegex(EffectUncertain, "reconcile"):
            self.execute(service)
        self.assertEqual(executor.actions, [])
        self.assertEqual(service._journal.lookup(ACTOR["domain"], self.item.effect_id),
                         ("unknown", None))
        service.close()

    def test_interruption_after_action_keeps_pending_unknown(self):
        executor = FakeExecutor()
        original = executor.perform

        def interrupted(request):
            original(request)
            raise KeyboardInterrupt("simulated process interruption")

        executor.perform = interrupted
        service = DurableEffectService(self.path, {"email": executor})
        with self.assertRaises(KeyboardInterrupt):
            self.execute(service)
        self.assertEqual(len(executor.actions), 1)
        service.close()
        restarted_executor = FakeExecutor()
        restarted = DurableEffectService(self.path, {"email": restarted_executor})
        with self.assertRaises(EffectUncertain):
            self.execute(restarted)
        self.assertEqual(restarted_executor.actions, [])
        restarted.close()

    def test_definite_failure_and_post_action_unknown_survive_restart(self):
        executor = FakeExecutor("before")
        service = DurableEffectService(self.path, {"email": executor})
        failed = self.execute(service, email.request(DEST, intent_id="failed"))
        self.assertEqual(failed.receipt.status, "failed")
        executor.fail_mode = "after"
        unknown = self.execute(service, email.request(DEST, intent_id="unknown"))
        self.assertEqual(unknown.receipt.status, "unknown")
        self.assertEqual(len(executor.actions), 1)
        service.close()
        restarted_executor = FakeExecutor()
        restarted = DurableEffectService(self.path, {"email": restarted_executor})
        for intent, prior in (("failed", failed), ("unknown", unknown)):
            replay = self.execute(restarted, email.request(DEST, intent_id=intent))
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.receipt, prior.receipt)
        self.assertEqual(restarted_executor.actions, [])
        restarted.close()

    def test_invalid_request_and_missing_disclosure_leave_no_intent(self):
        service = DurableEffectService(self.path, {"email": FakeExecutor()})
        forged = replace(self.item, effect_id="forged")
        with self.assertRaises(InvalidEffect):
            self.execute(service, forged)
        with self.assertRaises(AuthorityError):
            self.execute(service, disclosure_handle=None)
        self.assertIsNone(service._journal.lookup(ACTOR["domain"], self.item.effect_id))
        service.close()

    def test_provider_reconciles_action_after_restart_without_reexecution(self):
        provider = IdempotentProviderEmulator(self.provider_path, interrupt_after=True)
        service = DurableEffectService(self.path, {"email": provider})
        with self.assertRaises(KeyboardInterrupt):
            self.execute(service)
        self.assertEqual(provider.action_count(), 1)
        self.assertIsNone(service.receipt(ACTOR["domain"], self.item.effect_id))
        service.close()
        provider.close()

        reopened = IdempotentProviderEmulator(self.provider_path)
        service = DurableEffectService(self.path, {"email": reopened})
        with self.assertRaises(EffectUncertain):
            self.execute(service)
        receipt = service.reconcile(self.item, domain=ACTOR["domain"], now=NOW)
        self.assertEqual(receipt.status, "succeeded")
        self.assertEqual(receipt.external_ref, f"fake-provider:{self.item.effect_id}")
        self.assertEqual(receipt.authority_ids, (
            self.authority.describe(self.send).capability_id,
            self.authority.describe(self.disclose).capability_id))
        self.assertEqual(receipt.trace, self.item.trace)
        self.assertEqual(service.receipt(ACTOR["domain"], self.item.effect_id), receipt)
        self.assertEqual(self.execute(service).receipt, receipt)
        self.assertEqual(reopened.action_count(), 1)
        service.close()
        reopened.close()

    def test_absent_provider_record_remains_unknown_without_retry(self):
        provider = IdempotentProviderEmulator(self.provider_path)
        service = DurableEffectService(self.path, {"email": provider})
        metadata = _encoded_effect(EffectReceipt(
            self.item.effect_id, ACTOR["domain"], self.item.kind, self.item.destination,
            "unknown", None, "pending", (self.authority.describe(self.send).capability_id,),
            NOW, self.item.trace))
        self.assertTrue(service._journal.begin(ACTOR["domain"], self.item.effect_id, metadata))
        with self.assertRaises(EffectUncertain):
            service.reconcile(self.item, domain=ACTOR["domain"], now=NOW)
        self.assertEqual(service._journal.lookup(ACTOR["domain"], self.item.effect_id),
                         ("unknown", None))
        self.assertEqual(provider.action_count(), 0)
        service.close()
        provider.close()

    def test_reconciliation_does_not_reauthorize_revoked_action(self):
        provider = IdempotentProviderEmulator(self.provider_path, interrupt_after=True)
        service = DurableEffectService(self.path, {"email": provider})
        with self.assertRaises(KeyboardInterrupt):
            self.execute(service)
        self.authority.revoke(self.authority.describe(self.send).capability_id)
        receipt = service.reconcile(self.item, domain=ACTOR["domain"], now=NOW)
        self.assertEqual(receipt.status, "succeeded")
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.execute(service)
        self.assertEqual(provider.action_count(), 1)
        service.close()
        provider.close()

    def test_provider_rejects_same_id_with_altered_content(self):
        provider = IdempotentProviderEmulator(self.provider_path)
        provider.perform(self.item)
        with self.assertRaises(InvalidEffect):
            provider.lookup(replace(self.item, destination="other@example.com"))
        self.assertEqual(provider.action_count(), 1)
        provider.close()

    def test_old_journal_schema_keeps_pending_intent_uncertain(self):
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE effect_intents (domain TEXT NOT NULL, effect_id TEXT NOT NULL, "
                       "status TEXT NOT NULL, receipt TEXT, PRIMARY KEY(domain, effect_id))")
            db.execute("INSERT INTO effect_intents VALUES (?, ?, 'unknown', NULL)",
                       (ACTOR["domain"], self.item.effect_id))
        provider = IdempotentProviderEmulator(self.provider_path)
        service = DurableEffectService(self.path, {"email": provider})
        with self.assertRaisesRegex(EffectUncertain, "audit metadata"):
            service.reconcile(self.item, domain=ACTOR["domain"], now=NOW)
        self.assertEqual(provider.action_count(), 0)
        service.close()
        provider.close()


if __name__ == "__main__":
    unittest.main()
