"""Data-only IR. Graphs are descriptions, never Python plugin callbacks."""

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True)
class Node:
    id: str
    op: str
    inputs: tuple[str, ...] = ()
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...]

    @classmethod
    def from_json(cls, text: str) -> "Graph":
        """Parse an untrusted data graph without evaluating extension code."""
        if type(text) is not str or len(text) > 1_000_000:
            raise ValueError("graph must be JSON text below 1 MB")

        def object_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[key] = value
            return result

        raw = json.loads(text, object_pairs_hook=object_pairs,
                         parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        if type(raw) is not dict or set(raw) != {"nodes"} or type(raw["nodes"]) is not list or len(raw["nodes"]) > 1000:
            raise ValueError("graph must have at most 1000 nodes")
        nodes = []
        for entry in raw["nodes"]:
            if type(entry) is not dict or set(entry) != {"id", "op", "inputs", "config"}:
                raise ValueError("node must have id, op, inputs and config")
            if type(entry["id"]) is not str or type(entry["op"]) is not str or type(entry["inputs"]) is not list or type(entry["config"]) is not dict:
                raise ValueError("invalid node fields")
            if any(type(dep) is not str for dep in entry["inputs"]):
                raise ValueError("inputs must be node identifiers")
            nodes.append(Node(entry["id"], entry["op"], tuple(entry["inputs"]), entry["config"]))
        graph = cls(tuple(nodes))
        from .verifier import verify
        verify(graph)
        return graph


@dataclass(frozen=True)
class Observation:
    value: Any
    source: str
    label: str = "public"  # public | protected
    execution_id: str | None = None
    engine: str | None = None


@dataclass(frozen=True)
class TraceStep:
    node_id: str
    operation: str
    input_ids: tuple[str, ...]
    producer: str
    label: str
    source_ref: str | None = None
    execution_id: str | None = None
    engine: str | None = None
    state_version: int | None = None


@dataclass(frozen=True)
class Value:
    data: Any
    label: str
    sources: frozenset[str]
    trace: tuple[TraceStep, ...] = ()


@dataclass(frozen=True)
class Proposal:
    target: str
    value: Any
    base_version: int
    sources: frozenset[str]
    producer: str
    node_id: str
    proposal_id: str
    trace: tuple[TraceStep, ...] = ()


def _trace_payload(trace: tuple[TraceStep, ...]) -> list[dict[str, Any]]:
    if type(trace) is not tuple or not trace or any(type(step) is not TraceStep for step in trace):
        raise ValueError("trace must contain runtime steps")
    if len({step.node_id for step in trace}) != len(trace):
        raise ValueError("duplicate trace node")
    for step in trace:
        if any(type(field) is not str or not field.strip() for field in
               (step.node_id, step.operation, step.producer, step.label)):
            raise ValueError("invalid trace step")
        if type(step.input_ids) is not tuple or any(type(dep) is not str for dep in step.input_ids):
            raise ValueError("invalid trace inputs")
        if any(value is not None and (type(value) is not str or not value.strip())
               for value in (step.source_ref, step.execution_id, step.engine)):
            raise ValueError("invalid trace metadata")
        if step.state_version is not None and (type(step.state_version) is not int or step.state_version < 0):
            raise ValueError("invalid trace state version")
    return [asdict(step) for step in trace]


def proposal_identity(*, producer: str, node_id: str, target: str, value: Any,
                      base_version: int, sources: frozenset[str],
                      trace: tuple[TraceStep, ...]) -> str:
    """Deterministic identity for exact recomputation, not an authenticity proof."""
    payload = {"producer": producer, "node": node_id, "target": target,
               "value": value, "base_version": base_version, "sources": sorted(sources),
               "trace": _trace_payload(trace)}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CommitRequest:
    proposal: Proposal


@dataclass(frozen=True)
class DisclosureRequest:
    value: Any
    destination: str
    purpose: str
    sources: frozenset[str]
    trace: tuple[TraceStep, ...] = ()
    # This is a request, NOT an authorized or released value.


@dataclass(frozen=True)
class EffectRequest:
    kind: str
    destination: str
    payload: Any
    label: str
    disclosure: DisclosureRequest | None
    sources: frozenset[str]
    producer: str
    node_id: str
    intent_id: str
    effect_id: str
    trace: tuple[TraceStep, ...] = ()


def effect_identity(*, producer: str, node_id: str, intent_id: str, kind: str,
                    destination: str, payload: Any, label: str,
                    disclosure_purpose: str | None, sources: frozenset[str],
                    trace: tuple[TraceStep, ...]) -> str:
    """Stable identity for one material request and explicit user intent."""
    canonical = json.dumps({"producer": producer, "node": node_id,
                            "intent": intent_id, "kind": kind,
                            "destination": destination, "payload": payload,
                            "label": label, "disclosure_purpose": disclosure_purpose,
                            "sources": sorted(sources), "trace": _trace_payload(trace)}, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return sha256(canonical.encode("utf-8")).hexdigest()
