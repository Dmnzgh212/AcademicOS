"""Interpreter computes inert values and requests; it owns no state/effect executor."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .model import (CommitRequest, DisclosureRequest, EffectRequest, Graph,
                    Observation, Proposal, Value)
from .verifier import verify


def _json_value(value: Any, depth: int = 0) -> Any:
    """Copy the small JSON subset; reject arbitrary objects and executable values."""
    if depth > 32:
        raise ValueError("input exceeds maximum depth")
    if value is None or type(value) in (bool, int, float, str):
        if type(value) is float and (value != value or abs(value) == float("inf")):
            raise ValueError("non-finite number")
        return value
    if type(value) is list:
        return [_json_value(item, depth + 1) for item in value]
    if type(value) is dict and all(type(k) is str for k in value):
        return {k: _json_value(v, depth + 1) for k, v in value.items()}
    raise ValueError("only JSON values can enter PersonIR")


@dataclass(frozen=True)
class RunResult:
    outputs: dict[str, Any]
    proposals: tuple[Proposal, ...]
    commits: tuple[CommitRequest, ...]
    disclosures: tuple[DisclosureRequest, ...]
    effects: tuple[EffectRequest, ...]


class Interpreter:
    def run(self, graph: Graph, observations: dict[str, Observation], *, base_version: int) -> RunResult:
        verify(graph)
        if type(base_version) is not int or base_version < 0:
            raise ValueError("base_version must be a nonnegative integer")
        values: dict[str, Any] = {}
        outputs = {}
        proposals, commits, disclosures, effects = [], [], [], []
        for node in graph.nodes:
            args = [values[dep] for dep in node.inputs]
            config = node.config
            if node.op == "source":
                observation = observations[config["name"]]
                if not isinstance(observation, Observation) or observation.label != config["label"] or not observation.source:
                    raise ValueError(f"observation metadata mismatch: {node.id}")
                result = Value(_json_value(observation.value), observation.label, frozenset({observation.source}))
            elif node.op == "select":
                parent = args[0]
                if type(parent.data) is not dict:
                    raise ValueError(f"select requires object: {node.id}")
                result = Value(deepcopy(parent.data[config["key"]]), parent.label, parent.sources)
            elif node.op == "join":
                a, b = args
                result = Value([deepcopy(a.data), deepcopy(b.data)],
                               "protected" if "protected" in (a.label, b.label) else "public",
                               a.sources | b.sources)
            elif node.op == "derive":
                result = Value(deepcopy(args[0].data), args[0].label, args[0].sources)
            elif node.op == "propose":
                result = Proposal(config["target"], deepcopy(args[0].data), base_version, args[0].sources)
                proposals.append(result)
            elif node.op == "commit_request":
                result = CommitRequest(args[0])
                commits.append(result)
            elif node.op == "declassify":
                result = DisclosureRequest(deepcopy(args[0].data), config["destination"],
                                           config["purpose"], args[0].sources)
                disclosures.append(result)
            elif node.op == "effect_request":
                value = args[0]
                disclosure = value if isinstance(value, DisclosureRequest) else None
                result = EffectRequest(config["kind"], config["destination"],
                                       deepcopy(value.value if disclosure else value.data),
                                       "protected" if disclosure else value.label, disclosure,
                                       value.sources)
                effects.append(result)
            elif node.op == "output":
                result = args[0]
                outputs[node.id] = result
            values[node.id] = result
        return RunResult(outputs, tuple(proposals), tuple(commits), tuple(disclosures), tuple(effects))
