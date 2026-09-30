"""Trusted-host package boundary for a serialized PersonIR graph.

The host approves a manifest independently of the extension. Binding is not
capability issuance; StateStore and EffectService still check live grants.
"""

from dataclasses import dataclass
import json

from .model import Graph, Observation
from .runtime import Interpreter, RunResult
from .verifier import VerificationError, verify


@dataclass(frozen=True)
class PackageManifest:
    producer: str
    sources: frozenset[str]
    commit_targets: frozenset[str]
    effect_scopes: frozenset[tuple[str, str]]
    disclosures: frozenset[tuple[str, str]]  # (exact destination, purpose)

    def __post_init__(self):
        if type(self.producer) is not str or not self.producer.strip():
            raise ValueError("package producer and version required")
        for field in (self.sources, self.commit_targets, self.effect_scopes, self.disclosures):
            if type(field) is not frozenset:
                raise ValueError("manifest scopes must be frozensets")
        for name in self.sources | self.commit_targets:
            if type(name) is not str or not name.strip():
                raise ValueError("invalid manifest name")
        for scopes in (self.effect_scopes, self.disclosures):
            for pair in scopes:
                if (type(pair) is not tuple or len(pair) != 2 or
                        any(type(part) is not str or not part.strip() for part in pair)):
                    raise ValueError("manifest scopes require two nonempty strings")


class PackageRunner:
    """Host-only invocation; never hand its result or host objects to native plugins."""

    def __init__(self, manifest: PackageManifest, graph: Graph):
        if not isinstance(manifest, PackageManifest):
            raise TypeError("host-approved manifest required")
        verify(graph)
        # Snapshot mutable Node.config before validating scopes, so later caller
        # mutations cannot change the approved graph.
        encoded = json.dumps({"nodes": [
            {"id": node.id, "op": node.op, "inputs": list(node.inputs), "config": node.config}
            for node in graph.nodes
        ]}, allow_nan=False)
        self._graph = Graph.from_json(encoded)
        self.manifest = manifest
        for node in self._graph.nodes:
            config = node.config
            if node.op in {"source", "nondeterministic_source"} and config["name"] not in manifest.sources:
                raise VerificationError(f"source not declared: {config['name']}")
            if node.op == "propose" and config["target"] not in manifest.commit_targets:
                raise VerificationError(f"commit target not declared: {config['target']}")
            if node.op == "declassify" and (config["destination"], config["purpose"]) not in manifest.disclosures:
                raise VerificationError(f"disclosure not declared: {config['destination']}")
            if node.op == "effect_request" and (config["kind"], config["destination"]) not in manifest.effect_scopes:
                raise VerificationError(f"effect scope not declared: {config['kind']}:{config['destination']}")

    def run(self, observations: dict[str, Observation], *, base_version: int,
            intent_id: str = "default") -> RunResult:
        if type(observations) is not dict:
            raise TypeError("host observation map required")
        # Only named, approved inputs cross this boundary. In particular an
        # overprovided host map is never made available to the graph.
        names = {node.config["name"] for node in self._graph.nodes
                 if node.op in {"source", "nondeterministic_source"}}
        selected = {name: observations[name] for name in names}
        return Interpreter().run(self._graph, selected, base_version=base_version,
                                 producer=self.manifest.producer, intent_id=intent_id)
