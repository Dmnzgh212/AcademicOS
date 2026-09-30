import unittest

from experiments.person_ir import (AuthorityError, AuthorityStore, EffectService,
                                   FakeExecutor, Graph, Node, Observation,
                                   VerificationError)
from experiments.person_ir.examples import academic, email
from experiments.person_ir.package import PackageManifest, PackageRunner


class PackageBoundaryTests(unittest.TestCase):
    def test_academic_uses_approved_inputs_and_host_producer(self):
        manifest = PackageManifest("academic@1", frozenset({"deadline", "availability"}),
                                   frozenset({"study_blocks"}), frozenset(), frozenset())
        observations = {
            "deadline": Observation({"course": "CSI 2110"}, "course:1", "protected"),
            "availability": Observation({"free_slot": "Thursday"}, "calendar:1", "protected"),
            "overprovided": Observation("secret", "private:1", "protected"),
        }
        request = PackageRunner(manifest, academic.GRAPH).run(
            observations, base_version=0).commits[0]
        self.assertEqual(request.proposal.producer, "academic@1")
        self.assertEqual(request.proposal.sources, frozenset({"course:1", "calendar:1"}))
        self.assertNotIn("private:1", request.proposal.sources)

    def test_overprovided_input_cannot_expand_graph_access(self):
        graph = Graph((Node("read", "source", config={"name": "secret", "label": "protected"}),
                       Node("view", "output", ("read",))))
        manifest = PackageManifest("sample@1", frozenset({"public"}),
                                   frozenset(), frozenset(), frozenset())
        with self.assertRaisesRegex(VerificationError, "source not declared"):
            PackageRunner(manifest, graph)

    def test_unlisted_commit_effect_and_disclosure_are_rejected_at_binding(self):
        source = Node("value", "source", config={"name": "value", "label": "public"})
        manifest = PackageManifest("sample@1", frozenset({"value"}), frozenset(),
                                   frozenset(), frozenset())
        cases = [
            (Graph((source, Node("p", "propose", ("value",), {"target": "plan"}))),
             "commit target not declared"),
            (Graph((source, Node("send", "effect_request", ("value",),
                                 {"kind": "email", "destination": "alice"}))),
             "effect scope not declared"),
            (Graph((source, Node("d", "declassify", ("value",),
                                 {"destination": "alice", "purpose": "mail"}))),
             "disclosure not declared"),
        ]
        for graph, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(VerificationError, message):
                PackageRunner(manifest, graph)

    def test_approved_email_request_still_needs_live_grants(self):
        destination = "alice@example.com"
        manifest = PackageManifest("mail@1", frozenset({"context", "draft", "recipient"}),
                                   frozenset(), frozenset({("email", destination)}),
                                   frozenset({(destination, "send requested email")}))
        observations = {
            "context": Observation("meeting", "context:1", "protected"),
            "draft": Observation("hello", "draft:1", "protected"),
            "recipient": Observation(destination, "recipient:1"),
        }
        effect = PackageRunner(manifest, email.program(destination)).run(
            observations, base_version=0, intent_id="send:1").effects[0]
        self.assertEqual(effect.destination, destination)
        self.assertEqual(effect.producer, "mail@1")
        with self.assertRaises(AuthorityError):
            EffectService({"email": FakeExecutor()}).execute(
                effect, AuthorityStore(), object(), principal="person:1",
                domain="personal:1", agent="mail@1")

    def test_binding_snapshots_mutable_graph_config(self):
        source = Node("source", "source", config={"name": "public", "label": "public"})
        graph = Graph((source, Node("view", "output", ("source",))))
        manifest = PackageManifest("sample@1", frozenset({"public"}), frozenset(),
                                   frozenset(), frozenset())
        runner = PackageRunner(manifest, graph)
        source.config["name"] = "secret"
        result = runner.run({"public": Observation("safe", "host:public"),
                             "secret": Observation("private", "host:secret")},
                            base_version=0)
        self.assertEqual(result.outputs["view"].data, "safe")


if __name__ == "__main__":
    unittest.main()
