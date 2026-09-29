import unittest
import json

from experiments.person_ir import Graph, Node, Observation, Interpreter, VerificationError, verify
from experiments.person_ir.examples.academic import GRAPH, demo


class SliceOneTests(unittest.TestCase):
    def test_academic_end_to_end_remains_inert(self):
        result = demo()
        self.assertEqual(result.proposals[0].base_version, 3)
        self.assertEqual(result.proposals[0].value, ["CSI 2110", "Thursday 18:00"])
        self.assertEqual(result.proposals[0].sources, {"course-feed:42", "calendar:7"})
        self.assertEqual(result.commits[0].proposal, result.proposals[0])
        self.assertEqual(result.effects, ())

    def test_json_graph_ingress(self):
        serialized = json.dumps({"nodes": [{"id": "src", "op": "source", "inputs": [],
                                             "config": {"name": "message", "label": "public"}},
                                            {"id": "out", "op": "output", "inputs": ["src"], "config": {}}]})
        result = Interpreter().run(Graph.from_json(serialized),
                                   {"message": Observation("hello", "user", "public")}, base_version=0)
        self.assertEqual(result.outputs["out"].data, "hello")
        with self.assertRaises(ValueError):
            Graph.from_json('{"nodes":[],"nodes":[]}')

    def test_input_is_copied_and_non_data_rejected(self):
        deadline = {"course": "CSI 2110"}
        result = Interpreter().run(Graph((
            Node("src", "source", config={"name": "deadline", "label": "protected"}),
            Node("proposal", "propose", ("src",), {"target": "study_blocks"}),
        )), {"deadline": Observation(deadline, "course-feed", "protected")}, base_version=0)
        deadline["course"] = "changed"
        self.assertEqual(result.proposals[0].value["course"], "CSI 2110")
        with self.assertRaises(ValueError):
            Interpreter().run(GRAPH, {
                "deadline": Observation(lambda: None, "bad", "protected"),
                "availability": Observation({}, "calendar", "protected"),
            }, base_version=0)

    def test_unrecognized_callback_and_forward_reference_fail(self):
        with self.assertRaises(VerificationError):
            verify(Graph((Node("evil", "python_callback", config={"code": "open('/etc/passwd')"}),)))
        with self.assertRaises(VerificationError):
            verify(Graph((Node("p", "derive", ("future",)), Node("future", "source", config={"name": "x", "label": "public"}))))

    def test_protected_egress_requires_scoped_disclosure_request(self):
        src = Node("src", "source", config={"name": "private", "label": "protected"})
        direct = Node("send", "effect_request", ("src",), {"kind": "email", "destination": "alice"})
        with self.assertRaises(VerificationError):
            verify(Graph((src, direct)))
        disclose = Node("consent", "declassify", ("src",), {"destination": "alice", "purpose": "message"})
        with self.assertRaises(VerificationError):
            verify(Graph((src, disclose, Node("send", "effect_request", ("consent",),
                                              {"kind": "email", "destination": "bob"}))))
        result = Interpreter().run(Graph((src, disclose, direct.__class__(
            "send", "effect_request", ("consent",), {"kind": "email", "destination": "alice"}))),
            {"private": Observation("hello", "draft:1", "protected")}, base_version=0)
        self.assertEqual(result.effects[0].payload, "hello")
        self.assertEqual(result.effects[0].disclosure.purpose, "message")
        self.assertEqual(result.effects[0].sources, {"draft:1"})

    def test_label_claim_cannot_downgrade_host_observation(self):
        graph = Graph((Node("src", "source", config={"name": "secret", "label": "public"}),))
        with self.assertRaises(ValueError):
            Interpreter().run(graph, {"secret": Observation("x", "host", "protected")}, base_version=0)


if __name__ == "__main__":
    unittest.main()
