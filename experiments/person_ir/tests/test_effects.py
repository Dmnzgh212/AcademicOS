import unittest
from dataclasses import replace
from datetime import datetime, timezone

from experiments.person_ir import (AuthorityError, AuthorityStore, EffectService,
                                   FakeExecutor, Graph, Interpreter, InvalidEffect,
                                   Node, Observation, StateStore)


NOW = datetime(2026, 9, 29, 14, tzinfo=timezone.utc)
ACTOR = {"principal": "person:1", "domain": "personal:1", "agent": "plugin:mail"}


def request(payload="hello", *, intent="click:1", protected=True):
    label = "protected" if protected else "public"
    nodes = [Node("draft", "source", config={"name": "draft", "label": label})]
    source = "draft"
    if protected:
        nodes.append(Node("disclosure", "declassify", (source,),
                          {"destination": "alice@example.com", "purpose": "user message"}))
        source = "disclosure"
    nodes.append(Node("send", "effect_request", (source,),
                      {"kind": "email", "destination": "alice@example.com"}))
    return Interpreter().run(Graph(tuple(nodes)),
                             {"draft": Observation(payload, "draft:1", label)},
                             base_version=0, producer="mail@0.1", intent_id=intent).effects[0]


class EffectTests(unittest.TestCase):
    def setUp(self):
        self.authority = AuthorityStore()
        self.send = self.authority.issue(**(ACTOR | {"operation": "effect:email",
                                                   "resource": "alice@example.com",
                                                   "issuer": "person:1", "issued_at": NOW}))
        self.disclose = self.authority.issue(**(ACTOR | {"operation": "disclose",
                                                       "resource": "alice@example.com",
                                                       "purpose": "user message",
                                                       "issuer": "person:1", "issued_at": NOW}))
        self.executor = FakeExecutor()
        self.service = EffectService({"email": self.executor})

    def execute(self, item, **overrides):
        args = {"principal": ACTOR["principal"], "domain": ACTOR["domain"],
                "agent": ACTOR["agent"], "disclosure_handle": self.disclose,
                "now": NOW} | overrides
        return self.service.execute(item, self.authority, self.send, **args)

    def test_request_alone_has_no_action_and_missing_grants_block(self):
        item = request()
        self.assertEqual(self.executor.actions, [])
        with self.assertRaises(AuthorityError):
            self.execute(item, disclosure_handle=None)
        self.assertIsNone(self.service.receipt(ACTOR["domain"], item.effect_id))
        self.assertEqual(self.executor.actions, [])
        self.assertEqual(self.execute(item).receipt.status, "succeeded")
        self.assertEqual(len(self.executor.actions), 1)

    def test_same_identity_does_not_execute_twice_but_new_intent_can(self):
        first = self.execute(request())
        again = self.execute(request())
        self.assertTrue(again.replayed)
        self.assertEqual(again.receipt, first.receipt)
        self.assertEqual(len(self.executor.actions), 1)
        second = self.execute(request(intent="click:2"))
        self.assertNotEqual(first.receipt.effect_id, second.receipt.effect_id)
        self.assertEqual(len(self.executor.actions), 2)

    def test_material_change_has_new_identity_and_rechecks_authority(self):
        first = self.execute(request("price:10"))
        changed = request("price:11")
        self.assertNotEqual(changed.effect_id, first.receipt.effect_id)
        self.authority.revoke(self.authority.describe(self.send).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.execute(changed)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.execute(request("price:10"))
        self.assertEqual(len(self.executor.actions), 1)

    def test_rejected_and_uncertain_effects_have_distinct_terminal_receipts(self):
        self.executor.fail_mode = "before"
        rejected = self.execute(request("reject"))
        self.assertEqual(rejected.receipt.status, "failed")
        self.assertEqual(len(self.executor.actions), 0)
        self.executor.fail_mode = None
        self.assertTrue(self.execute(request("reject")).replayed)
        self.assertEqual(len(self.executor.actions), 0)
        self.executor.fail_mode = "after"
        uncertain = self.execute(request("uncertain"))
        self.assertEqual(uncertain.receipt.status, "unknown")
        self.assertEqual(len(self.executor.actions), 1)
        self.executor.fail_mode = None
        self.assertTrue(self.execute(request("uncertain")).replayed)
        self.assertEqual(len(self.executor.actions), 1)
        self.assertEqual(self.execute(request("success")).receipt.status, "succeeded")
        self.assertEqual(len(self.executor.actions), 2)

    def test_tampered_request_rejected_without_execution(self):
        item = replace(request(protected=False), payload="different")
        with self.assertRaises(InvalidEffect):
            self.execute(item)
        self.assertEqual(self.executor.actions, [])

    def test_local_state_change_does_not_undo_external_action(self):
        self.execute(request("send"))
        state = StateStore(ACTOR["domain"], {"draft": "send"})
        commit_grant = self.authority.issue(**(ACTOR | {"operation": "commit", "resource": "draft",
                                                         "issuer": "person:1", "issued_at": NOW}))
        graph = Graph((Node("source", "source", config={"name": "value", "label": "public"}),
                       Node("proposal", "propose", ("source",), {"target": "draft"}),
                       Node("commit", "commit_request", ("proposal",))))
        commit_request = Interpreter().run(graph, {"value": Observation("cancelled", "user")},
                                           base_version=state.snapshot().version).commits[0]
        state.commit(commit_request, self.authority, commit_grant,
                     principal=ACTOR["principal"], agent=ACTOR["agent"], now=NOW)
        self.assertEqual(state.snapshot().values["draft"], "cancelled")
        self.assertEqual(len(self.executor.actions), 1)
        # No rollback API or transaction spans the fake external action and state.
        self.assertEqual(self.executor.actions[0].payload, "send")


if __name__ == "__main__":
    unittest.main()
