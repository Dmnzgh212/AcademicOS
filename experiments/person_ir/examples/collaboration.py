"""Shared-state proposal exposing a missing multi-principal authority rule."""

from experiments.person_ir import Graph, Interpreter, Node, Observation


GRAPH = Graph((
    Node("document", "source", config={"name": "document", "label": "protected"}),
    Node("approvals", "source", config={"name": "approvals", "label": "public"}),
    Node("suggestion", "join", ("document", "approvals")),
    Node("proposal", "propose", ("suggestion",), {"target": "shared_document"}),
    Node("commit", "commit_request", ("proposal",)),
))


def request(approvals: list[str]):
    return Interpreter().run(GRAPH, {
        "document": Observation("Revised project scope", "shared-doc:1", "protected"),
        "approvals": Observation(approvals, "approval-claim:1", "public"),
    }, base_version=0, producer="collaboration-example@1").commits[0]
