import unittest
from datetime import datetime, timezone

from experiments.person_ir import (AuthorityStore, EffectService, FakeExecutor,
                                   Interpreter, Observation, StateStore)
from experiments.person_ir.baseline import (ComponentSession, Manifest,
                                            academic_component, email_component)
from experiments.person_ir.examples import academic, email


NOW = datetime(2026, 9, 29, 19, tzinfo=timezone.utc)


class ConventionalHostAPITests(unittest.TestCase):
    def test_academic_same_result_and_host_commit_semantics(self):
        observations = {
            "deadline": Observation({"course": "CSI 2110"}, "course:1", "protected"),
            "availability": Observation({"free_slot": "Thursday"}, "calendar:1", "protected"),
        }
        manifest = Manifest("academic@1", frozenset(observations),
                            frozenset({"study_blocks"}), frozenset())
        conventional = academic_component(ComponentSession(manifest, observations, base_version=0))
        graph = Interpreter().run(academic.GRAPH, observations, base_version=0,
                                  producer="academic@1").commits[0]
        self.assertEqual(conventional.proposal.value, graph.proposal.value)
        self.assertEqual(conventional.proposal.sources, graph.proposal.sources)
        authority = AuthorityStore()
        handle = authority.issue(principal="person:1", domain="personal:1",
                                 agent="academic@1", operation="commit",
                                 resource="study_blocks", issuer="person:1", issued_at=NOW)
        for item in (conventional, graph):
            state = StateStore("personal:1")
            result = state.commit(item, authority, handle,
                                  principal="person:1", agent="academic@1", now=NOW)
            self.assertTrue(result.receipt.applied)
            self.assertEqual(state.snapshot().values["study_blocks"], ["CSI 2110", "Thursday"])

    def test_email_same_authority_and_replay_contract(self):
        destination = "alice@example.com"
        observations = {
            "context": Observation("meeting", "context:1", "protected"),
            "draft": Observation("hello", "draft:1", "protected"),
            "recipient": Observation(destination, "recipient:1", "public"),
        }
        manifest = Manifest("mail@1", frozenset(observations), frozenset(),
                            frozenset({("email", destination)}))
        conventional = email_component(ComponentSession(manifest, observations,
                                                         base_version=0, intent_id="send:1"), destination)
        graph = Interpreter().run(email.program(destination), observations,
                                  base_version=0, producer="mail@1", intent_id="send:1").effects[0]
        self.assertEqual(conventional.payload, graph.payload)
        authority = AuthorityStore()
        args = {"principal": "person:1", "domain": "personal:1", "agent": "mail@1",
                "resource": destination, "issuer": "person:1", "issued_at": NOW}
        send = authority.issue(**(args | {"operation": "effect:email"}))
        disclose = authority.issue(**(args | {"operation": "disclose",
                                              "purpose": "send requested email"}))
        for item in (conventional, graph):
            executor = FakeExecutor()
            service = EffectService({"email": executor})
            first = service.execute(item, authority, send, principal="person:1",
                                    domain="personal:1", agent="mail@1",
                                    disclosure_handle=disclose, now=NOW)
            second = service.execute(item, authority, send, principal="person:1",
                                     domain="personal:1", agent="mail@1",
                                     disclosure_handle=disclose, now=NOW)
            self.assertEqual(first.receipt.status, "succeeded")
            self.assertTrue(second.replayed)
            self.assertEqual(len(executor.actions), 1)

    def test_manifest_restricts_inputs_and_effect_scope(self):
        observations = {"public": Observation("ok", "host:public"),
                        "secret": Observation("private", "host:secret", "protected")}
        session = ComponentSession(Manifest("sample@1", frozenset({"public"}),
                                            frozenset(), frozenset({("email", "alice")})),
                                   observations, base_version=0)
        self.assertEqual(session.read("public"), "ok")
        with self.assertRaisesRegex(PermissionError, "source not declared"):
            session.read("secret")
        with self.assertRaisesRegex(PermissionError, "effect scope not declared"):
            session.effect("email", "bob", "hello")

    def test_protected_read_requires_disclosure_and_code_can_check_recipient(self):
        observations = {
            "context": Observation("meeting", "context:1", "protected"),
            "draft": Observation("hello", "draft:1", "protected"),
            "recipient": Observation("bob", "recipient:1"),
        }
        manifest = Manifest("mail@1", frozenset(observations), frozenset(),
                            frozenset({("email", "alice")}))
        session = ComponentSession(manifest, observations, base_version=0)
        with self.assertRaisesRegex(ValueError, "recipient and destination differ"):
            email_component(session, "alice")
        with self.assertRaisesRegex(PermissionError, "disclosure purpose"):
            session.effect("email", "alice", "hello")


if __name__ == "__main__":
    unittest.main()
