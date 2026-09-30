# PersonIR falsification experiment — decision record

Date: 2026-09-30. Decision owner: research prototype team. Scope: the small executable PersonIR and conventional host comparisons in this repository; **not** a judgment that LifeHub should stop, or that every possible person-oriented language is impossible.

## Decision

**No-Go for a new PersonIR source language or compiler now. Reduce PersonIR to an optional, data-only format for inspectable flows and explanations. Build LifeHub's open extension platform around host-owned capabilities, package/input binding, versioned state, explicit effect requests, and use-time policy.** Do not make the experimental Python interpreter or the WIT draft a production security boundary.

This is a decision under limited evidence, not a claim that a full Component Model comparison or real-provider trial has been completed. The burden for starting a compiler is affirmative evidence of a meaningful advantage. That burden was not met; more simulated adapters do not change it. The seven planned slices and the present comparator are enough to decide **what not to fund next**. Unresolved product safety work remains mandatory before exposing hostile extensions or real effects.

## Decision gate against the original plan

| Plan criterion | Observed evidence | Decision implication |
|---|---|---|
| Three heterogeneous scenarios benefit from the same small IR primitives | Academic, email, payment, device, and collaboration can represent observations, proposals, and requests. Payment freshness/ceilings, device predicates, recipient equality, and shared governance need host rules or domain policy. `derive` currently copies rather than expressing arbitrary decision logic. | Representation generalizes; a **semantic or safety advantage** in three domains is not demonstrated. |
| Hostile attempts rejected without domain-specific kernel rules | The serialized graph rejects unknown ops, direct protected effects, forged handles, stale commits, and request tampering. `PackageRunner` binds declared sources/scopes. Native direct-service request forgery works if untrusted code reaches trusted Python APIs and valid handles. | Useful closed-graph protection, with a narrower threat boundary than an open hostile-plugin platform. |
| Conventional component baseline reveals a meaningful advantage | The ordinary host API shares grant, state, policy, and effect services. Two executable core-WASM programs now use a common host import set and enter the same Python services. PersonIR retains finer node-level lineage for its closed operations; the ordinary component expresses recipient equality directly. | No demonstrated advantage large enough to justify a compiler. A real Component/WIT binary, broader parity, and comparable authoring costs remain untested. |
| User-facing capability/effect explanations derivable from a program | Trace steps, source refs, grant IDs, and receipts are inspectable internally. No user-facing explanation UI or comprehension study exists. Source metadata are host claims, not attestations. | A useful design direction, not a passed user-facing gate. |
| Small kernel stays free of a life ontology | Ten generic graph operations cover data movement. Domain checks remain outside IR. Adding conditional, transform, and evidence semantics would expand the language; keeping them outside weakens its claimed uniqueness. | Keep the representation small and optional; do not freeze syntax or turn the kernel into a domain ontology. |

The original plan requires the *continue* criteria collectively. Several are unproven or fail in the current slice, so a compiler is not justified. This does not require proving that ordinary WASM/WIT is superior on every dimension. It requires refusing to claim an unobserved PersonIR advantage.

## What the experiment did establish

- Requests can be separated from commits/effects. Local state uses version checks and receipts; fake effects use live grants, disclosure checks, and replay ledgers. These mechanisms also work with conventional host request objects.
- A closed data graph offers inspectable node lineage and can structurally reject a direct protected-to-effect edge within its threat model. The trusted host still supplies labels and observes local outputs.
- Durable SQLite probes retain grant revocation, commit audits, and effect intents. A separate **fake** provider ledger can reconcile a known action after host interruption; absence of a record stays unknown. No real-provider exactly-once guarantee follows.
- `shared:` state probes enforce a configured set of principals even through direct store calls. Approval strings and signatures of the actual people are not authenticated here.
- Host policy can reject named recipient, amount, quote, and sensor counterexamples. The policy approval and evidence origin are trusted external inputs.

## Rejected or narrowed claims

| Proposed claim | Decision |
|---|---|
| POP is an established new programming paradigm | Reject as an established fact; retain as a research label. |
| PersonIR requires a new source language/compiler | Reject for this implementation and evidence. |
| Hash-linked traces authenticate observation origin or approval | Reject. They bind content under host assertions and can be recomputed by a direct API caller. |
| A verified graph alone secures an open plugin platform | Reject. Host API isolation, package approval, protected-output handling, runtime policy, and real effects are separate boundaries. |
| External effects are exactly once or rolled back with local state | Reject. Only same-ID fake-host replay and a narrow fake-provider reconciliation were tested. |
| Person-associated durable state, delegated authority, explicit effects, and provenance are useless | Reject this overstatement. The composition is a viable **product architecture hypothesis**, mostly on established mechanisms. |

`THREAT_MODEL.md`, `PERSON_IR_SPEC.md`, `SCENARIO_FINDINGS.md`, and `BASELINE_COMPARISON.md` hold the detailed limits. The 83 focused tests are executable evidence, not a formal proof. The local Python construction benchmark is an implementation microbenchmark; it is not a comparative WASM performance result.

## Implementation direction after this decision

1. **LifeHub host:** define a versioned, approved package/input contract and isolate extension execution from capability issuance, raw state/effect services, and protected local outputs. Treat every commit/effect as a host operation with a fresh use-time check.
2. **Data and authority:** persist domain policy, grants, revocations, state versions, and audit receipts with authenticated startup/session handoff. Define policy approval, evidence origin, migration, and deletion rules before relying on the data in high-impact actions.
3. **External effects:** before connecting email, payment, or devices, choose adapters with documented idempotency/status behavior and an operator-visible `unknown` reconciliation path. Require a separate review for irreversible actions.
4. **PersonIR, if used:** confine it to an optional graph/provenance view or a small declarative automation subset. Keep conventional extension code and host APIs first-class. Avoid announcing a new language or compiler as a product prerequisite.

These are concrete next engineering programs, **not prerequisites for the No-Go decision**. They should have their own milestones and acceptance tests.

## What would reopen the compiler decision

Reopen only with a reproducible, feature-comparable experiment: at least three distinct domains using the same small IR without domain nodes or arbitrary callbacks; hostile execution with a real isolated host boundary; a running Component/WIT or equivalent capability-limited comparator using the same policies/effects; and measured improvement in an outcome such as reliable user explanations or structurally prevented errors that the comparator cannot achieve at similar cost. Record ergonomics and runtime overhead on comparable terms. A design sketch or another fake executor does not meet this bar.

## Artifact checklist

The plan's nine expected artifacts are present in this branch: this decision record; `PERSON_IR_SPEC.md`; interpreter/runtime and verifier with negative tests; five scenario programs; the conventional Python and core-WASM baselines; `BASELINE_COMPARISON.md`; `THREAT_MODEL.md`; and the rejected/narrowed-claims ledger above. The preferred Component/WIT comparator is represented by an **uncompiled WIT candidate**, not a completed executable result. The decision is therefore explicit and reviewable while that optional preferred implementation and the separate product safety work remain open.
