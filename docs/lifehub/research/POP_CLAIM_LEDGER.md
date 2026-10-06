# POP / LifeHub claim ledger — 2026-09-28

This ledger prevents research hypotheses from silently becoming product facts.

## Status vocabulary

- Established in repository — demonstrated by current code/tests/docs.
- Prior art — known idea LifeHub may reuse but should not claim as an invention.
- Combination hypothesis — potentially distinctive composition; novelty not established.
- Research hypothesis — requires formalization/experiment.
- Invalid if stated absolutely — useful intuition that becomes false or misleading without scope.
- Open evidence gap — requires further research.

## Ledger

| Claim | Status | Notes |
|---|---|---|
| v0.2 has arbitrary string extension points rather than a kernel-owned closed list | Established in repository | Registry/manifest design and v0.2 audit support this. |
| Cross-plugin reads require request + local grant and can be revoked | Established in repository | Current capability broker behavior. |
| Current web board is not the definition of LifeHub | Established design direction | Workspace consumes generic extension references. |
| Current runtime safely executes arbitrary hostile third-party code | False / not established | Existing docs explicitly say the host API boundary is not an OS sandbox. |
| Local-first/user-owned data is novel | Prior art | Do not market as invention. |
| Capability security is novel | Prior art | Reuse it. |
| Provenance/event history is novel | Prior art | Reuse it. |
| Effect typing is novel | Prior art | Reuse effect-system research. |
| Information-flow control is novel | Prior art | Reuse IFC/DIFC research. |
| Plugin manifests/contribution points are novel | Prior art | Existing extensible platforms cover this. |
| Personal data stores with isolated third-party apps are novel | Prior art | Databox and related systems are important predecessors. |
| Personal data can never leave the machine | Invalid if stated absolutely | Legitimate communication and external actions require authorized egress. |
| Personal data cannot silently egress | Combination hypothesis | Requires explicit declassification/effect semantics and a threat model. |
| Software proposes; the person commits | Invalid if stated absolutely | Delegated automation is legitimate. Valid authority may commit/execute. |
| Proposal/Commit is a useful thin waist | Research hypothesis | Compare with transactions/MVCC/event sourcing/capability hosts. |
| Person-associated durable state should outlive apps | Product/system thesis | Needs migration/deletion/versioning semantics. |
| Authority should be explicitly delegated and revocable | Product/system thesis on prior-art foundations | Test integration with state/effects/provenance. |
| Observation -> Interpretation -> Proposal -> Authority is useful | Combination hypothesis | Test across non-calendar domains. |
| A new source-language syntax is required | Not established | Do not build parser/compiler first. |
| A small verified PersonIR may be useful | Research hypothesis | Build verifier/interpreter experiment first. |
| PersonIR can statically infer all permissions | Invalid if stated absolutely | Dynamic state and revocation require runtime enforcement. |
| Verified IR automatically makes the system secure | Invalid | Verifier/runtime/OS remain part of the trusted computing base. |
| Event sourcing can roll back external effects | Invalid | Email/payment/physical actions may be irreversible. |
| Core should know no life domains | Strong design rule | Ecosystem still needs versioned semantic contracts. |
| Ontology belongs to the ecosystem, not the kernel | Combination/design thesis | Validate with independently evolving contracts. |
| POP is an established programming paradigm | Not established | Treat as a working research label. |
| No prior system has the same model | Open evidence gap | Do not claim absence without a completed, scoped prior-art review. |
| The combination of person-associated durable state + delegated authority + provenance + proposal/commit + explicit effects + open extensions is technically distinctive | Combination hypothesis | Needs direct prior-art search and implementation evidence. |
| LifeHub is fundamentally a calendar/planner | False framing | Calendar is only a stress case/application. |
| AcademicOS is the conceptual parent of LifeHub | False future architecture | AcademicOS should become an integration/package collection if the platform matures. |

## Claims to try to kill

1. Proposal/Commit is more than transaction terminology.
2. Person-associated authority belongs in the computation model rather than only the host API.
3. Provenance should be first-class in the IR rather than external tracing.
4. Effect-as-data materially improves safety/auditability beyond ordinary typed host APIs.
5. The model generalizes beyond planning.
6. The model remains open without forcing a central ontology.

## Standard for future novelty language

Prefer “candidate”, “working hypothesis”, “within the systems reviewed”, “combination may be distinctive”, and “not yet established”.

Avoid “new paradigm”, “first ever”, “fundamentally unprecedented”, and “proved secure” until evidence supports the exact scoped statement.
