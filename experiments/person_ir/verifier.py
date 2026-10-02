"""Structural checks before interpreting a data-only graph."""

from __future__ import annotations

import json

from .model import Program


class VerificationError(ValueError):
    pass


# Exact allowed fields and input counts keep control flow and host authority finite.
SHAPES: dict[str, tuple[int, frozenset[str]]] = {
    "observe": (0, frozenset({"source", "label"})),
    "state_view": (0, frozenset({"source", "label"})),
    "transform": (1, frozenset({"op", "key"})),
    "join": (2, frozenset()),
    "derive": (1, frozenset()),
    "declassify": (1, frozenset({"destination", "purpose"})),
    "propose": (1, frozenset({"namespace", "key"})),
    "commit_request": (1, frozenset()),
    "effect_request": (1, frozenset({"kind", "destination", "purpose"})),
    "output": (1, frozenset()),
}
TERMINAL = {"commit_request", "effect_request", "output"}


def verify(program: Program) -> None:
    if not isinstance(program, Program) or not isinstance(program.name, str) or not program.name:
        raise VerificationError("program must have a name")
    if not program.nodes:
        raise VerificationError("program has no nodes")
    seen: dict[str, str] = {}
    for node in program.nodes:
        if not isinstance(node.id, str) or not node.id or node.id in seen:
            raise VerificationError("node IDs must be unique nonempty strings")
        if node.kind not in SHAPES:
            raise VerificationError(f"unknown node kind: {node.kind}")
        count, fields = SHAPES[node.kind]
        if type(node.inputs) is not tuple or len(node.inputs) != count:
            raise VerificationError(f"{node.id}: wrong input count")
        if any(type(reference) is not str for reference in node.inputs):
            raise VerificationError(f"{node.id}: input IDs must be strings")
        if any(reference not in seen or seen[reference] in TERMINAL for reference in node.inputs):
            raise VerificationError(f"{node.id}: input must refer to an earlier value node")
        if node.kind == "commit_request" and seen[node.inputs[0]] != "propose":
            raise VerificationError(f"{node.id}: commit request must reference a proposal")
        if type(node.parameters) is not dict or set(node.parameters) != fields:
            raise VerificationError(f"{node.id}: wrong parameters")
        if any(type(value) is not str or not value for value in node.parameters.values()):
            raise VerificationError(f"{node.id}: parameters must be nonempty strings")
        if node.kind in {"observe", "state_view"} and node.parameters["label"] not in {
            "public",
            "protected",
        }:
            raise VerificationError(f"{node.id}: unknown label")
        if node.kind == "transform" and node.parameters["op"] not in {"identity", "get"}:
            raise VerificationError(f"{node.id}: unknown transform")
        if (
            node.kind == "transform"
            and node.parameters["op"] == "identity"
            and node.parameters["key"] != "-"
        ):
            raise VerificationError(f"{node.id}: identity key must be '-'")
        seen[node.id] = node.kind
    if not any(node.kind in TERMINAL for node in program.nodes):
        raise VerificationError("program has no output or request")
    # Never accept Python objects embedded as inputs or parameters.
    try:
        json.dumps([(node.id, node.kind, node.inputs, node.parameters) for node in program.nodes])
    except (TypeError, ValueError) as exc:
        raise VerificationError("graph must contain JSON data only") from exc
