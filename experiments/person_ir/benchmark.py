"""Small, reproducible Python API overhead probe; not a sandbox benchmark."""

from statistics import median
from timeit import repeat

from experiments.person_ir import Interpreter, Observation
from experiments.person_ir.baseline import (ComponentSession, Manifest,
                                            academic_component, email_component)
from experiments.person_ir.examples import academic, email


def measure(rounds: int = 5, number: int = 2000) -> dict[str, float]:
    academic_inputs = {
        "deadline": Observation({"course": "CSI 2110"}, "course:1", "protected"),
        "availability": Observation({"free_slot": "Thursday"}, "calendar:1", "protected"),
    }
    email_inputs = {
        "context": Observation("meeting", "context:1", "protected"),
        "draft": Observation("hello", "draft:1", "protected"),
        "recipient": Observation("alice", "recipient:1", "public"),
    }
    academic_manifest = Manifest("academic@1", frozenset(academic_inputs),
                                 frozenset({"study_blocks"}), frozenset())
    email_manifest = Manifest("mail@1", frozenset(email_inputs), frozenset(),
                              frozenset({("email", "alice")}))
    email_graph = email.program("alice")
    interpreter = Interpreter()
    cases = {
        "academic_graph": lambda: interpreter.run(academic.GRAPH, academic_inputs,
                                                  base_version=0, producer="academic@1"),
        "academic_host_api": lambda: academic_component(
            ComponentSession(academic_manifest, academic_inputs, base_version=0)),
        "email_graph": lambda: interpreter.run(email_graph, email_inputs,
                                               base_version=0, producer="mail@1"),
        "email_host_api": lambda: email_component(
            ComponentSession(email_manifest, email_inputs, base_version=0), "alice"),
    }
    return {name: median(repeat(fn, repeat=rounds, number=number)) * 1_000_000 / number
            for name, fn in cases.items()}


if __name__ == "__main__":
    for name, microseconds in measure().items():
        print(f"{name}: {microseconds:.2f} us/op")
