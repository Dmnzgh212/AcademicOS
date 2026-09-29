"""Adversarial matrix: rejection reasons and deliberately reproduced gaps."""

import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone

from experiments.person_ir import (AuthorityError, AuthorityStore, EffectService,
                                   FakeExecutor, Graph, Interpreter, Node, Observation,
                                   StaleProposal, StateStore, VerificationError)
from experiments.person_ir.examples import email
from experiments.person_ir.model import effect_identity


NOW = datetime(2026, 9, 29, 18, tzinfo=timezone.utc)
ACTOR = {"principal": "person:1", "domain": "personal:1", "agent": "plugin:mail"}


def grant(store, operation, resource, purpose=None):
    return store.issue(**(ACTOR | {"operation": operation, "resource": resource,
                                 "purpose": purpose, "issuer": "person:1", "issued_at": NOW}))


class HostileExtensionTests(unittest.TestCase):
    def test_unknown_state_node_and_callback_cannot_enter_json_ir(self):
        for op in ("state_read", "python_callback", "network", "subprocess"):
            graph = json.dumps({"nodes": [{"id": "attack", "op": op,
                                           "inputs": [], "config": {}}]})
            with self.subTest(op=op), self.assertRaisesRegex(VerificationError, "unsupported"):
                Graph.from_json(graph)

    def test_serialized_capability_metadata_is_not_a_handle(self):
        authority = AuthorityStore()
        actual = grant(authority, "effect:email", "alice@example.com")
        forged = json.loads(json.dumps({"capability_id": authority.describe(actual).capability_id}))
        with self.assertRaisesRegex(AuthorityError, "unknown capability handle"):
            authority.check_effect_request(email.request("alice@example.com"), forged,
                                           **ACTOR, now=NOW)

    def test_protected_egress_cannot_skip_disclosure_or_change_destination(self):
        source = Node("secret", "source", config={"name": "secret", "label": "protected"})
        direct = Node("send", "effect_request", ("secret",),
                      {"kind": "email", "destination": "alice@example.com"})
        with self.assertRaisesRegex(VerificationError, "protected effect"):
            Interpreter().run(Graph((source, direct)),
                              {"secret": Observation("private", "host", "protected")},
                              base_version=0)
        disclose = Node("d", "declassify", ("secret",),
                        {"destination": "alice@example.com", "purpose": "message"})
        mismatched = Node("send", "effect_request", ("d",),
                          {"kind": "email", "destination": "bob@example.com"})
        with self.assertRaisesRegex(VerificationError, "destination mismatch"):
            Graph.from_json(json.dumps({"nodes": [
                {"id": n.id, "op": n.op, "inputs": list(n.inputs), "config": n.config}
                for n in (source, disclose, mismatched)]}))

    def test_replay_and_scope_mismatch_do_not_act_again(self):
        authority, executor = AuthorityStore(), FakeExecutor()
        service = EffectService({"email": executor})
        item = email.request("alice@example.com")
        wrong = grant(authority, "effect:email", "bob@example.com")
        disclose = grant(authority, "disclose", "alice@example.com", "send requested email")
        with self.assertRaisesRegex(AuthorityError, "scope mismatch"):
            service.execute(item, authority, wrong, **ACTOR,
                            disclosure_handle=disclose, now=NOW)
        correct = grant(authority, "effect:email", "alice@example.com")
        first = service.execute(item, authority, correct, **ACTOR,
                                disclosure_handle=disclose, now=NOW)
        second = service.execute(item, authority, correct, **ACTOR,
                                 disclosure_handle=disclose, now=NOW)
        self.assertEqual(first.receipt, second.receipt)
        self.assertTrue(second.replayed)
        self.assertEqual(len(executor.actions), 1)

    def test_stale_commit_is_rejected(self):
        state, authority = StateStore("personal:1"), AuthorityStore()
        handle = grant(authority, "commit", "plan")
        graph = Graph((Node("value", "source", config={"name": "value", "label": "public"}),
                       Node("proposal", "propose", ("value",), {"target": "plan"}),
                       Node("commit", "commit_request", ("proposal",))))
        def item(value):
            return Interpreter().run(graph, {"value": Observation(value, "user")},
                                     base_version=0).commits[0]
        state.commit(item("first"), authority, handle,
                     principal="person:1", agent="plugin:mail", now=NOW)
        with self.assertRaises(StaleProposal):
            state.commit(item("second"), authority, handle,
                         principal="person:1", agent="plugin:mail", now=NOW)

    def test_overprovided_observation_is_readable_by_a_graph_known_gap(self):
        # There is no manifest/allowed-source binding in the interpreter. The
        # trusted caller must filter its input map and keep local outputs private.
        graph = Graph((Node("read", "source", config={"name": "secret", "label": "protected"}),
                       Node("view", "output", ("read",))))
        result = Interpreter().run(graph, {
            "public": Observation("safe", "host:public"),
            "secret": Observation("overprovided", "host:secret", "protected"),
        }, base_version=0)
        self.assertEqual(result.outputs["view"].data, "overprovided")

    def test_graph_has_no_package_capability_declaration_known_gap(self):
        # The grant is checked, but there is no independent manifest request.
        graph = Graph.from_json(json.dumps({"nodes": [
            {"id": "input", "op": "source", "inputs": [],
             "config": {"name": "payload", "label": "public"}},
            {"id": "send", "op": "effect_request", "inputs": ["input"],
             "config": {"kind": "email", "destination": "unlisted@example.com"}},
        ]}))
        item = Interpreter().run(graph, {"payload": Observation("test", "host:1")},
                                 base_version=0).effects[0]
        authority, executor = AuthorityStore(), FakeExecutor()
        handle = grant(authority, "effect:email", "unlisted@example.com")
        receipt = EffectService({"email": executor}).execute(
            item, authority, handle, **ACTOR, now=NOW).receipt
        self.assertEqual(receipt.status, "succeeded")
        self.assertEqual(len(executor.actions), 1)

    def test_direct_api_can_forge_provenance_with_a_new_hash_known_gap(self):
        # Graph-only code cannot construct this object. A native plugin with
        # access to EffectService could recompute the public hash and lie.
        original = email.request("alice@example.com")
        forged_trace = (replace(original.trace[0], source_ref="invented-source"),
                        *original.trace[1:])
        forged_disclosure = replace(original.disclosure, value="forged message")
        forged_id = effect_identity(
            producer=original.producer, node_id=original.node_id,
            intent_id=original.intent_id, kind=original.kind,
            destination=original.destination, payload="forged message",
            label=original.label, disclosure_purpose=forged_disclosure.purpose,
            sources=original.sources, trace=forged_trace)
        forged = replace(original, payload="forged message", disclosure=forged_disclosure,
                         trace=forged_trace, effect_id=forged_id)
        authority, executor = AuthorityStore(), FakeExecutor()
        send = grant(authority, "effect:email", "alice@example.com")
        disclose = grant(authority, "disclose", "alice@example.com", "send requested email")
        receipt = EffectService({"email": executor}).execute(
            forged, authority, send, **ACTOR, disclosure_handle=disclose, now=NOW).receipt
        self.assertEqual(receipt.status, "succeeded")
        self.assertEqual(receipt.trace[0].source_ref, "invented-source")


if __name__ == "__main__":
    unittest.main()
