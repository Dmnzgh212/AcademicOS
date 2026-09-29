import unittest
from dataclasses import replace
from datetime import datetime, timezone

from experiments.person_ir import (AuthorityStore, EffectService, FakeExecutor,
                                   Graph, Interpreter, InvalidEffect, InvalidProposal,
                                   Node, Observation,
                                   StateStore, VerificationError, verify)
from experiments.person_ir.model import CommitRequest


NOW = datetime(2026, 9, 29, 15, tzinfo=timezone.utc)


class ProvenanceFlowTests(unittest.TestCase):
    def test_join_propagates_label_and_lineage_to_proposal_receipt(self):
        graph = Graph((
            Node("private", "source", config={"name": "private", "label": "protected"}),
            Node("public", "source", config={"name": "public", "label": "public"}),
            Node("joined", "join", ("private", "public")),
            Node("derived", "derive", ("joined",)),
            Node("proposal", "propose", ("derived",), {"target": "plan"}),
            Node("commit", "commit_request", ("proposal",)),
            Node("view", "output", ("derived",)),
        ))
        run = Interpreter().run(graph, {
            "private": Observation("deadline", "course:1", "protected"),
            "public": Observation("free slot", "calendar:1", "public"),
        }, base_version=0, producer="academic@2")
        self.assertEqual(run.outputs["view"].label, "protected")
        proposal = run.proposals[0]
        self.assertEqual(proposal.sources, {"course:1", "calendar:1"})
        self.assertEqual([step.node_id for step in proposal.trace],
                         ["private", "public", "joined", "derived", "proposal"])
        self.assertEqual(proposal.trace[-1].state_version, 0)
        self.assertTrue(all(step.producer == "academic@2" for step in proposal.trace))
        state = StateStore("personal:1")
        authority = AuthorityStore()
        handle = authority.issue(principal="person:1", domain="personal:1",
                                 agent="plugin:academic", operation="commit", resource="plan",
                                 issuer="person:1", issued_at=NOW)
        forged_trace = (replace(proposal.trace[0], source_ref="forged"), *proposal.trace[1:])
        forged = CommitRequest(replace(proposal, trace=forged_trace))
        with self.assertRaises(InvalidProposal):
            state.commit(forged, authority, handle, principal="person:1",
                         agent="plugin:academic", now=NOW)
        receipt = state.commit(run.commits[0], authority, handle, principal="person:1",
                               agent="plugin:academic", now=NOW).receipt
        self.assertEqual(receipt.trace, proposal.trace)
        self.assertEqual(receipt.sources, {"course:1", "calendar:1"})
        self.assertEqual(receipt.authority_id, authority.describe(handle).capability_id)
        self.assertEqual(proposal.trace[0].source_ref, "course:1")

    def test_declassification_path_and_grants_are_visible_in_effect_receipt(self):
        graph = Graph((
            Node("source", "source", config={"name": "draft", "label": "protected"}),
            Node("disclose", "declassify", ("source",),
                 {"destination": "alice@example.com", "purpose": "requested email"}),
            Node("send", "effect_request", ("disclose",),
                 {"kind": "email", "destination": "alice@example.com"}),
        ))
        item = Interpreter().run(graph, {"draft": Observation("hello", "draft:1", "protected")},
                                 base_version=3, producer="mail@2", intent_id="click:1").effects[0]
        self.assertEqual([step.operation for step in item.trace],
                         ["source", "declassify", "effect_request"])
        authority = AuthorityStore()
        common = {"principal": "person:1", "domain": "personal:1", "agent": "plugin:mail",
                  "resource": "alice@example.com", "issuer": "person:1", "issued_at": NOW}
        effect_handle = authority.issue(**(common | {"operation": "effect:email"}))
        disclosure_handle = authority.issue(**(common | {"operation": "disclose",
                                                       "purpose": "requested email"}))
        service = EffectService({"email": FakeExecutor()})
        with self.assertRaises(InvalidEffect):
            service.execute(replace(item, trace=(replace(item.trace[0], source_ref="forged"),
                                                 *item.trace[1:])),
                            authority, effect_handle, principal="person:1", domain="personal:1",
                            agent="plugin:mail", disclosure_handle=disclosure_handle, now=NOW)
        receipt = service.execute(
            item, authority, effect_handle, principal="person:1", domain="personal:1",
            agent="plugin:mail", disclosure_handle=disclosure_handle, now=NOW).receipt
        self.assertEqual(len(receipt.authority_ids), 2)
        self.assertEqual(receipt.trace, item.trace)
        self.assertEqual(item.disclosure.purpose, "requested email")

    def test_direct_join_egress_and_bypass_are_rejected(self):
        source = Node("s", "source", config={"name": "secret", "label": "protected"})
        public = Node("p", "source", config={"name": "public", "label": "public"})
        join = Node("j", "join", ("s", "p"))
        with self.assertRaises(VerificationError):
            verify(Graph((source, public, join,
                          Node("send", "effect_request", ("j",),
                               {"kind": "email", "destination": "alice"}))))
        disclosure = Node("d", "declassify", ("j",),
                          {"destination": "alice", "purpose": "user email"})
        with self.assertRaises(VerificationError):
            verify(Graph((source, public, join, disclosure,
                          Node("bypass", "derive", ("d",)))))
        with self.assertRaises(VerificationError):
            verify(Graph((source, public, join, disclosure,
                          Node("send", "effect_request", ("d",),
                               {"kind": "email", "destination": "bob"}))))
        with self.assertRaises(VerificationError):
            verify(Graph((Node("forged", "source", config={"name": "x", "label": "public",
                                                        "source_ref": "made-up"}),)))

    def test_nondeterministic_input_requires_execution_metadata(self):
        graph = Graph((Node("model_result", "nondeterministic_source",
                            config={"name": "answer", "label": "protected"}),
                       Node("view", "output", ("model_result",))))
        with self.assertRaisesRegex(ValueError, "execution metadata"):
            Interpreter().run(graph, {"answer": Observation("suggestion", "ai:run", "protected")},
                              base_version=0)
        result = Interpreter().run(graph, {
            "answer": Observation("suggestion", "ai:run", "protected",
                                  execution_id="run:42", engine="model:v3")}, base_version=0)
        source_step = result.outputs["view"].trace[0]
        self.assertEqual(source_step.operation, "nondeterministic_source")
        self.assertEqual((source_step.execution_id, source_step.engine), ("run:42", "model:v3"))


if __name__ == "__main__":
    unittest.main()
