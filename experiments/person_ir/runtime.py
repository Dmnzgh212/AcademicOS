"""Pure evaluation; requests are returned as data for a separate authority layer."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .model import Program
from .verifier import verify


@dataclass(frozen=True)
class Value:
    data: Any
    sources: frozenset[str]
    label: str
    disclosures: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Intent:
    kind: str
    node_id: str
    data: Any
    sources: frozenset[str]
    parameters: dict[str, str]
    label: str
    disclosures: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Result:
    values: dict[str, Value]
    intents: tuple[Intent, ...]


class Interpreter:
    def run(
        self,
        program: Program,
        observations: Mapping[str, Any],
        state_views: Mapping[str, Any] | None = None,
    ) -> Result:
        verify(program)

        # Deep-copy and JSON-check the host boundary. In particular, no callback or
        # object with an ambient filesystem/network method may enter as a value.
        def snapshot(value: Any) -> Any:
            return json.loads(json.dumps(value, allow_nan=False))

        values: dict[str, Value] = {}
        nodes_by_id = {node.id: node for node in program.nodes}
        intents: list[Intent] = []
        state_views = state_views or {}
        for node in program.nodes:
            p = node.parameters
            if node.kind in {"observe", "state_view"}:
                source = p["source"]
                host_values = observations if node.kind == "observe" else state_views
                if source not in host_values:
                    raise KeyError(f"missing host input: {source}")
                values[node.id] = Value(
                    snapshot(host_values[source]), frozenset({source}), p["label"]
                )
                continue
            parents = [values[ref] for ref in node.inputs]
            parent = parents[0]
            if node.kind == "transform":
                if p["op"] == "get":
                    if not isinstance(parent.data, dict) or p["key"] not in parent.data:
                        raise ValueError(f"{node.id}: missing object key")
                    data = snapshot(parent.data[p["key"]])
                else:
                    data = snapshot(parent.data)
                values[node.id] = Value(data, parent.sources, parent.label, parent.disclosures)
            elif node.kind == "join":
                other = parents[1]
                values[node.id] = Value(
                    [snapshot(parent.data), snapshot(other.data)],
                    parent.sources | other.sources,
                    "protected" if "protected" in {parent.label, other.label} else "public",
                    parent.disclosures + other.disclosures,
                )
            elif node.kind == "derive":
                values[node.id] = Value(
                    snapshot(parent.data), parent.sources, parent.label, parent.disclosures
                )
            elif node.kind == "declassify":
                values[node.id] = Value(
                    snapshot(parent.data),
                    parent.sources,
                    "public",
                    parent.disclosures + ((p["destination"], p["purpose"]),),
                )
            else:
                if node.kind == "effect_request" and (
                    parent.label == "protected"
                    or any(destination != p["destination"] for destination, _ in parent.disclosures)
                ):
                    raise ValueError("protected effect needs matching disclosure")
                parameters = (
                    dict(nodes_by_id[node.inputs[0]].parameters)
                    if node.kind == "commit_request"
                    else dict(p)
                )
                if node.kind == "propose":
                    values[node.id] = Value(
                        snapshot(parent.data), parent.sources, parent.label, parent.disclosures
                    )
                else:
                    intents.append(
                        Intent(
                            node.kind,
                            node.id,
                            snapshot(parent.data),
                            parent.sources,
                            parameters,
                            parent.label,
                            parent.disclosures,
                        )
                    )
        return Result(copy.deepcopy(values), tuple(copy.deepcopy(intents)))
