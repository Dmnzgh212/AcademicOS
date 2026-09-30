import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from experiments.person_ir import AuthorityError, FakeExecutor, Interpreter, Observation
from experiments.person_ir.durable import (DurableAuthorityStore, DurableEffectService,
                                           DurableStateStore)
from experiments.person_ir.examples import academic, email


NOW = datetime(2026, 9, 30, 6, tzinfo=timezone.utc)
DEST = "alice@example.com"
ACTOR = {"principal": "person:1", "domain": "personal:1", "agent": "mail@1"}


class DurableAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "host.sqlite")
        self.request = email.request(DEST, intent_id="durable-grant:1")

    def issue(self, store, operation, purpose=None, expires_at=None):
        return store.issue(**(ACTOR | {
            "operation": operation, "resource": DEST, "issuer": "person:1",
            "issued_at": NOW, "purpose": purpose, "expires_at": expires_at}))

    def check(self, store, send, disclose, when=NOW):
        return store.check_effect_request(self.request, send, **ACTOR,
                                          disclosure_handle=disclose, now=when)

    def test_restart_recovers_fresh_handles_and_revocation(self):
        store = DurableAuthorityStore(self.path)
        send = self.issue(store, "effect:email")
        disclose = self.issue(store, "disclose", "send requested email")
        send_id = store.describe(send).capability_id
        disclosure_id = store.describe(disclose).capability_id
        self.assertEqual(len(self.check(store, send, disclose).capability_ids), 2)
        store.close()

        restarted = DurableAuthorityStore(self.path)
        recovered = restarted.host_handles()
        self.assertIsNot(recovered[send_id], send)
        with self.assertRaisesRegex(AuthorityError, "unknown capability handle"):
            self.check(restarted, send_id, recovered[disclosure_id])
        with self.assertRaisesRegex(AuthorityError, "unknown capability handle"):
            self.check(restarted, send, recovered[disclosure_id])
        self.check(restarted, recovered[send_id], recovered[disclosure_id])
        restarted.revoke(send_id)
        restarted.close()

        third = DurableAuthorityStore(self.path)
        handles = third.host_handles()
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.check(third, handles[send_id], handles[disclosure_id])
        third.close()

    def test_cross_instance_revocation_and_expiry_are_checked_at_use(self):
        first = DurableAuthorityStore(self.path)
        send = self.issue(first, "effect:email", expires_at=NOW + timedelta(minutes=1))
        disclose = self.issue(first, "disclose", "send requested email")
        send_id, disclosure_id = (first.describe(item).capability_id
                                  for item in (send, disclose))
        second = DurableAuthorityStore(self.path)
        handles = second.host_handles()
        with self.assertRaisesRegex(AuthorityError, "outside validity"):
            self.check(second, handles[send_id], handles[disclosure_id],
                       NOW + timedelta(minutes=1))
        first.revoke(disclosure_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.check(second, handles[send_id], handles[disclosure_id])
        first.close()
        second.close()

    def test_effect_receipt_replays_after_both_registries_restart(self):
        authority = DurableAuthorityStore(self.path)
        send = self.issue(authority, "effect:email")
        disclose = self.issue(authority, "disclose", "send requested email")
        send_id, disclosure_id = (authority.describe(item).capability_id
                                  for item in (send, disclose))
        service = DurableEffectService(self.path, {"email": FakeExecutor()})
        first = service.execute(self.request, authority, send, **ACTOR,
                                disclosure_handle=disclose, now=NOW)
        service.close()
        authority.close()

        authority = DurableAuthorityStore(self.path)
        handles = authority.host_handles()
        executor = FakeExecutor()
        service = DurableEffectService(self.path, {"email": executor})
        replay = service.execute(self.request, authority, handles[send_id], **ACTOR,
                                 disclosure_handle=handles[disclosure_id], now=NOW)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, first.receipt)
        self.assertEqual(executor.actions, [])
        authority.revoke(send_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            service.execute(self.request, authority, handles[send_id], **ACTOR,
                            disclosure_handle=handles[disclosure_id], now=NOW)
        service.close()
        authority.close()

    def test_local_commit_and_grant_share_database(self):
        observations = {
            "deadline": Observation({"course": "CSI 2110"}, "course:1", "protected"),
            "availability": Observation({"free_slot": "Thursday"}, "calendar:1", "protected"),
        }
        request = Interpreter().run(academic.GRAPH, observations, base_version=0,
                                    producer="academic@1").commits[0]
        authority = DurableAuthorityStore(self.path)
        handle = authority.issue(principal="person:1", domain="personal:1",
                                 agent="academic@1", operation="commit",
                                 resource="study_blocks", issuer="person:1",
                                 issued_at=NOW)
        identifier = authority.describe(handle).capability_id
        state = DurableStateStore(self.path, "personal:1")
        first = state.commit(request, authority, handle, principal="person:1",
                             agent="academic@1", now=NOW)
        state.close()
        authority.close()
        authority = DurableAuthorityStore(self.path)
        state = DurableStateStore(self.path, "personal:1")
        replay = state.commit(request, authority, authority.host_handles()[identifier],
                              principal="person:1", agent="academic@1", now=NOW)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, first.receipt)
        authority.revoke(identifier)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            state.commit(request, authority, authority.host_handles()[identifier],
                         principal="person:1", agent="academic@1", now=NOW)
        state.close()
        authority.close()


if __name__ == "__main__":
    unittest.main()
