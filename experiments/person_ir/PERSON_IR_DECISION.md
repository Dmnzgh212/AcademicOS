# PersonIR decision — 2026-10-03

Status: **No-Go for a new PersonIR source language/compiler on current evidence.**

This record converges the stacked PersonIR experiment through the conventional Wasm baseline with the independent conclusion already recorded in PR #2. It is deliberately scoped: it does not reject LifeHub, and it does not prove that every possible future IR is unnecessary.

## Decision

Do not begin a PersonIR parser, source language, compiler, or production execution path.

Keep the capability-limited Wasm host as the current executable third-party boundary. Keep the PersonIR graph/verifier only as experimental evidence and, at most, a candidate optional declarative policy/workflow/explanation layer.

## Why

The original handoff required PersonIR to beat a conventional capability runtime on meaningful semantics or enforcement before language/compiler work.

The current experiment does not clear that gate:

- heterogeneous scenarios reuse request plumbing, but planning, freshness, payment/device policy, and multi-principal collaboration remain host/domain responsibilities;
- hostile tests found that native trusted-host code can reconstruct an `Intent` while preserving a misleading trace, so graph verification alone is not an end-to-end authority/provenance boundary;
- the existing bounded core-Wasm host already stages local proposals and external effect requests without granting direct durable mutation or external execution;
- proposal/commit and effect separation therefore do not require a new language;
- PersonIR's strongest demonstrated distinction is finer inspectable graph lineage and structural protected-flow checking inside a tiny closed operation set;
- no representative performance, developer-productivity, or generality advantage has been demonstrated.

## What survives

The following ideas remain useful, but should be treated as platform mechanisms or prior-art-backed safety patterns rather than proof of a new programming model:

- package identity and approval;
- explicit capabilities and revocation;
- host-mediated storage/network/effects;
- staged local mutation with base-version checks;
- durable effect intent/outcome records;
- explicit disclosure policy where protected data leaves a local boundary;
- provenance/audit records where they materially improve explanation or policy;
- replaceable local review/decision surfaces.

## Reopen criteria

Reopen compiler work only with a reproducible comparison showing at least one important property that a conventional capability-limited Wasm/component host cannot reasonably provide with similar clarity and complexity.

A future comparison should use the same dynamic workload, threat model, authority lifecycle, provenance requirements, and external-effect semantics on both sides. A claim based only on nicer syntax, more explicit naming, or graph visualization is insufficient.

## Relationship to LifeHub

Failure of the compiler hypothesis is a successful falsification result, not a failure of LifeHub.

LifeHub's platform thesis remains: unknown third-party capabilities should enter through a stable, mediated, capability-limited boundary without teaching Core a closed list of life domains.
