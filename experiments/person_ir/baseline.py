"""Conventional component-to-host API sketch, sharing host request services.

This is an API-model comparator, not an executable untrusted-code sandbox.
Trusted sample functions stand in for a separately isolated component.
"""

from dataclasses import dataclass
from typing import Any

from .model import (CommitRequest, DisclosureRequest, EffectRequest, Observation,
                    Proposal, TraceStep, effect_identity, proposal_identity)
from .runtime import _json_value


@dataclass(frozen=True)
class Manifest:
    component_id: str
    sources: frozenset[str]
    commit_targets: frozenset[str]
    effect_scopes: frozenset[tuple[str, str]]  # (kind, exact destination)


class ComponentSession:
    """Host-mediated input and request interface for a declared component."""

    def __init__(self, manifest: Manifest, observations: dict[str, Observation], *,
                 base_version: int, intent_id: str = "default"):
        if not isinstance(manifest, Manifest) or not manifest.component_id:
            raise ValueError("component manifest required")
        if type(base_version) is not int or base_version < 0:
            raise ValueError("valid base version required")
        if type(intent_id) is not str or not intent_id.strip():
            raise ValueError("intent ID required")
        self.manifest = manifest
        self._observations = observations  # trusted host owns this mapping
        self.base_version = base_version
        self.intent_id = intent_id
        self._reads: list[TraceStep] = []
        self._sources: set[str] = set()
        self._protected = False

    def read(self, name: str) -> Any:
        if name not in self.manifest.sources:
            raise PermissionError(f"source not declared: {name}")
        observation = self._observations[name]
        if not isinstance(observation, Observation) or observation.label not in {"public", "protected"}:
            raise ValueError("invalid host observation")
        if type(observation.source) is not str or not observation.source.strip():
            raise ValueError("source reference required")
        self._sources.add(observation.source)
        self._protected |= observation.label == "protected"
        self._reads.append(TraceStep(f"read:{len(self._reads)}", "host_read", (),
                                     self.manifest.component_id, observation.label,
                                     observation.source, observation.execution_id,
                                     observation.engine))
        return _json_value(observation.value)

    def propose(self, target: str, value: Any) -> CommitRequest:
        if target not in self.manifest.commit_targets:
            raise PermissionError(f"commit target not declared: {target}")
        data = _json_value(value)
        sources = frozenset(self._sources)
        trace = (*self._reads, TraceStep("proposal", "host_proposal", (),
                                        self.manifest.component_id,
                                        "protected" if self._protected else "public",
                                        state_version=self.base_version))
        proposal = Proposal(target, data, self.base_version, sources,
                            self.manifest.component_id, "proposal",
                            proposal_identity(producer=self.manifest.component_id,
                                              node_id="proposal", target=target, value=data,
                                              base_version=self.base_version,
                                              sources=sources, trace=trace), trace)
        return CommitRequest(proposal)

    def effect(self, kind: str, destination: str, payload: Any, *,
               disclosure_purpose: str | None = None) -> EffectRequest:
        if (kind, destination) not in self.manifest.effect_scopes:
            raise PermissionError(f"effect scope not declared: {kind}:{destination}")
        data = _json_value(payload)
        sources = frozenset(self._sources)
        disclosure = None
        if self._protected:
            if type(disclosure_purpose) is not str or not disclosure_purpose.strip():
                raise PermissionError("protected data requires declared disclosure purpose")
            disclosure_trace = (*self._reads,
                                TraceStep("disclosure", "host_disclosure", (),
                                          self.manifest.component_id, "protected"))
            disclosure = DisclosureRequest(data, destination, disclosure_purpose,
                                           sources, disclosure_trace)
        label = "protected" if self._protected else "public"
        trace = (*(disclosure.trace if disclosure else self._reads),
                 TraceStep("effect", "host_effect", (), self.manifest.component_id, label))
        identity = effect_identity(producer=self.manifest.component_id, node_id="effect",
                                   intent_id=self.intent_id, kind=kind,
                                   destination=destination, payload=data, label=label,
                                   disclosure_purpose=disclosure_purpose if disclosure else None,
                                   sources=sources, trace=trace)
        return EffectRequest(kind, destination, data, label, disclosure, sources,
                             self.manifest.component_id, "effect", self.intent_id,
                             identity, trace)


def academic_component(session: ComponentSession) -> CommitRequest:
    deadline = session.read("deadline")
    availability = session.read("availability")
    return session.propose("study_blocks", [deadline["course"], availability["free_slot"]])


def email_component(session: ComponentSession, destination: str) -> EffectRequest:
    context = session.read("context")
    draft = session.read("draft")
    recipient = session.read("recipient")
    if recipient != destination:
        raise ValueError("recipient and destination differ")
    return session.effect("email", destination, [[context, draft], recipient],
                          disclosure_purpose="send requested email")
