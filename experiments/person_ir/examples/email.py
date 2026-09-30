"""Intentional personal-context egress through a scoped disclosure request."""

from experiments.person_ir import Graph, Interpreter, Node, Observation


def program(destination: str) -> Graph:
    return Graph((
        Node("context", "source", config={"name": "context", "label": "protected"}),
        Node("draft", "source", config={"name": "draft", "label": "protected"}),
        Node("recipient", "source", config={"name": "recipient", "label": "public"}),
        Node("message", "join", ("context", "draft")),
        Node("addressed", "join", ("message", "recipient")),
        Node("disclose", "declassify", ("addressed",),
             {"destination": destination, "purpose": "send requested email"}),
        Node("send", "effect_request", ("disclose",),
             {"kind": "email", "destination": destination}),
    ))


def request(destination: str, *, intent_id: str = "send:1"):
    return Interpreter().run(program(destination), {
        "context": Observation("course meeting", "user:context", "protected"),
        "draft": Observation("See you tomorrow", "draft:1", "protected"),
        "recipient": Observation(destination, "recipient:1", "public"),
    }, base_version=0, producer="email-example@1", intent_id=intent_id).effects[0]
