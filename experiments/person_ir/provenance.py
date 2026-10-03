"""Inspectable lineage for values and intents; supplied evidence is host-asserted."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Evidence:
    source: str
    observation_id: str
    producer: str
    producer_version: str
    security_label: str | None = None
    state_version: int | None = None
    deterministic: bool = True
    execution_id: str | None = None

    def validate(self) -> None:
        if not all(
            type(value) is str and value
            for value in (self.source, self.observation_id, self.producer, self.producer_version)
        ):
            raise ValueError("evidence identity and producer are required")
        if self.state_version is not None and (
            type(self.state_version) is not int or self.state_version < 0
        ):
            raise ValueError("state version must be nonnegative")
        if self.security_label is not None and self.security_label not in {"public", "protected"}:
            raise ValueError("unknown host security label")
        if type(self.deterministic) is not bool:
            raise ValueError("determinism must be a boolean")
        if not self.deterministic and (type(self.execution_id) is not str or not self.execution_id):
            raise ValueError("nondeterministic evidence requires execution metadata")


@dataclass(frozen=True)
class Trace:
    program: str
    program_version: str
    evidence: tuple[Evidence, ...]
    steps: tuple[str, ...]
    disclosures: tuple[tuple[str, str, str], ...] = ()

    def step(self, identity: str) -> Trace:
        return replace(self, steps=self.steps + (identity,))

    def release(self, destination: str, scope: str, purpose: str) -> Trace:
        return replace(
            self,
            disclosures=self.disclosures + ((destination, scope, purpose),),
        )

    def join(self, other: Trace, identity: str) -> Trace:
        if (self.program, self.program_version) != (other.program, other.program_version):
            raise ValueError("cannot join different program runs")
        evidence = {item.source: item for item in self.evidence}
        for item in other.evidence:
            if item.source in evidence and item != evidence[item.source]:
                raise ValueError("conflicting evidence for the same source")
            evidence[item.source] = item
        steps = tuple(dict.fromkeys(self.steps + other.steps)) + (identity,)
        return Trace(
            self.program,
            self.program_version,
            tuple(evidence[key] for key in sorted(evidence)),
            steps,
            self.disclosures + other.disclosures,
        )
