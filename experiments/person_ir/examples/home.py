"""Sensor and policy data become a device request; no predicate/freshness rule yet."""

from experiments.person_ir import Graph, Interpreter, Node, Observation


GRAPH = Graph((
    Node("sensor", "nondeterministic_source", config={"name": "sensor", "label": "public"}),
    Node("policy", "source", config={"name": "policy", "label": "public"}),
    Node("command", "join", ("sensor", "policy")),
    Node("activate", "effect_request", ("command",),
         {"kind": "device", "destination": "thermostat:1"}),
))


def request(temperature: int, *, intent_id: str = "home:1"):
    return Interpreter().run(GRAPH, {
        "sensor": Observation({"celsius": temperature}, "sensor:thermostat:1", "public",
                              execution_id="reading:1", engine="thermometer:v1"),
        "policy": Observation({"cool_above_celsius": 25}, "policy:1", "public"),
    }, base_version=0, producer="home-example@1", intent_id=intent_id).effects[0]
