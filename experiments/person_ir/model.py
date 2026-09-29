"""Data-only IR. Graphs are descriptions, never Python plugin callbacks."""

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class Value:
    data: Any
    label: str
    sources: frozenset[str]


@dataclass(frozen=True)
class Proposal:
    target: str
    value: Any
    base_version: int
    sources: frozenset[str]
    producer: str
    node_id: str
    proposal_id: str


def proposal_identity(*, producer: str, node_id: str, target: str, value: Any,
                      base_version: int, sources: frozenset[str]) -> str:
    """Deterministic identity for exact recomputation, not an authenticity proof."""
    payload = {"producer": producer, "node": node_id, "target": target,
               "value": value, "base_version": base_version, "sources": sorted(sources)}
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
    # This is a request, NOT an authorized or released value.


@dataclass(frozen=True)
class EffectRequest:
    kind: str
    destination: str
    payload: Any
    label: str
    disclosure: DisclosureRequest | None
    sources: frozenset[str]
