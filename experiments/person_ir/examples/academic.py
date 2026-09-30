"""Academic observation to local study proposal. No calendar mutation occurs."""

from experiments.person_ir import Graph, Node, Observation, Interpreter


GRAPH = Graph((
    Node("deadline", "source", config={"name": "deadline", "label": "protected"}),
    Node("availability", "source", config={"name": "availability", "label": "protected"}),
    Node("course", "select", ("deadline",), {"key": "course"}),
    Node("slot", "select", ("availability",), {"key": "free_slot"}),
    Node("plan", "join", ("course", "slot")),
    Node("suggestion", "derive", ("plan",)),
    Node("proposal", "propose", ("suggestion",), {"target": "study_blocks"}),
    Node("request", "commit_request", ("proposal",)),
    Node("show", "output", ("proposal",)),
))


def demo():
    return Interpreter().run(GRAPH, {
        "deadline": Observation({"course": "CSI 2110", "due": "Friday"}, "course-feed:42", "protected"),
        "availability": Observation({"free_slot": "Thursday 18:00"}, "calendar:7", "protected"),
    }, base_version=3)
