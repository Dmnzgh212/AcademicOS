import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from experiments.person_ir import AuthorityError, AuthorityStore, FakeExecutor, InvalidEffect
from experiments.person_ir.durable import DurableEffectJournal, DurableEffectService
from experiments.person_ir.effects import EffectUncertain
from experiments.person_ir.examples import email


NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)
DEST = "alice@example.com"
ACTOR = {"principal": "person:1", "domain": "personal:1", "agent": "mail@1"}


class DurableEffectServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "effects.sqlite")
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


if __name__ == "__main__":
    unittest.main()
