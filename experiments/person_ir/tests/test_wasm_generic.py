import unittest
from datetime import datetime, timezone

from experiments.person_ir import (AuthorityError, AuthorityStore, EffectService,
                                   FakeExecutor, Observation, StateStore)
from experiments.person_ir.package import PackageManifest
from experiments.person_ir.wasm_bridge import WasmRequestRejected
from experiments.person_ir.wasm_generic_bridge import request_from_generic_wasm


NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)
DEST = "alice@example.com"


class GenericCoreWasmTests(unittest.TestCase):
    def test_academic_uses_shared_import_abi_and_normal_state_commit(self):
        observations = {
            "deadline": Observation({"course": "CSI 2110"}, "course:1", "protected"),
            "availability": Observation({"free_slot": "Thursday"}, "calendar:1", "protected"),
        }
        manifest = PackageManifest("academic@1", frozenset(observations),
                                   frozenset({"study_blocks"}), frozenset(), frozenset())
        request = request_from_generic_wasm("academic", manifest, observations)
        self.assertEqual(request.proposal.value, ["CSI 2110", "Thursday"])
        authority = AuthorityStore()
        handle = authority.issue(principal="person:1", domain="personal:1",
                                 agent="academic@1", operation="commit",
                                 resource="study_blocks", issuer="person:1", issued_at=NOW)
        state = StateStore("personal:1")
        outcome = state.commit(request, authority, handle,
                               principal="person:1", agent="academic@1", now=NOW)
        self.assertEqual(outcome.receipt.authority_ids,
                         (authority.describe(handle).capability_id,))
        self.assertEqual(state.snapshot().values["study_blocks"], request.proposal.value)

    def test_email_uses_same_abi_and_live_effect_grants(self):
        observations = {
            "context": Observation("meeting", "context:1", "protected"),
            "draft": Observation("hello", "draft:1", "protected"),
            "recipient": Observation(DEST, "recipient:1", "public"),
        }
        manifest = PackageManifest("mail@1", frozenset(observations), frozenset(),
                                   frozenset({("email", DEST)}),
                                   frozenset({(DEST, "send requested email")}))
        item = request_from_generic_wasm("email", manifest, observations,
                                         destination=DEST, intent_id="send:1")
        authority = AuthorityStore()
        args = {"principal": "person:1", "domain": "personal:1", "agent": "mail@1",
                "resource": DEST, "issuer": "person:1", "issued_at": NOW}
        send = authority.issue(**(args | {"operation": "effect:email"}))
        disclose = authority.issue(**(args | {"operation": "disclose",
                                              "purpose": "send requested email"}))
        executor = FakeExecutor()
        service = EffectService({"email": executor})
        kwargs = dict(principal="person:1", domain="personal:1", agent="mail@1",
                      disclosure_handle=disclose, now=NOW)
        first = service.execute(item, authority, send, **kwargs)
        self.assertEqual(first.receipt.status, "succeeded")
        self.assertTrue(service.execute(item, authority, send, **kwargs).replayed)
        self.assertEqual(len(executor.actions), 1)
        authority.revoke(authority.describe(send).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            service.execute(item, authority, send, **kwargs)

    def test_generic_abi_rejects_undeclared_and_forged_values(self):
        observations = {
            "context": Observation("meeting", "context:1", "protected"),
            "draft": Observation("hello", "draft:1", "protected"),
            "recipient": Observation(DEST, "recipient:1", "public"),
        }
        manifest = PackageManifest("mail@1", frozenset(observations), frozenset(),
                                   frozenset({("email", DEST)}),
                                   frozenset({(DEST, "send requested email")}))
        for mutation in ({"sourceIndex": 3}, {"forgeHandle": True}):
            with self.subTest(mutation=mutation), self.assertRaises(WasmRequestRejected):
                request_from_generic_wasm("email", manifest, observations,
                                          destination=DEST, mutation=mutation)
        mismatch = observations | {"recipient": Observation("bob@example.com", "recipient:1")}
        with self.assertRaises(WasmRequestRejected):
            request_from_generic_wasm("email", manifest, mismatch, destination=DEST,
                                      mutation={"skipEquality": True})


if __name__ == "__main__":
    unittest.main()
