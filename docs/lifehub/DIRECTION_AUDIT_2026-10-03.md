# LifeHub direction audit — 2026-10-03

Status: **convergence audit after PersonIR falsification slices and the conventional Wasm baseline**.

This audit checks the current work against the 2026-09-28 handoff. It is intentionally conservative: code volume, passing tests, and conceptual elegance are not evidence that a research hypothesis belongs in the product architecture.

## Strict conclusion

**Direction is still broadly correct, but the implementation process became temporarily out of order. No irreversible architecture drift has reached `main`.**

The important correction is now explicit:

- LifeHub remains the open personal-computing platform.
- The executable third-party boundary should continue around a capability-limited Wasm host.
- PersonIR is **not** justified as a new source language/compiler by the current evidence.
- Proposal/commit, effect staging, package approval, and review surfaces may remain useful **conventional host mechanisms**. Their usefulness does not prove POP/PersonIR.
- The review inbox is a replaceable reference shell, not the definition of LifeHub.
- PersonIR should remain an experiment/optional declarative policy or explanation layer unless later evidence demonstrates an enforcement or explanatory advantage that a conventional host cannot reasonably reproduce.

## Evidence checked

Repository anchors at audit time:

- `main` remains at `856b48a7adbb480d567d63c2582aa02d7405ce92`.
- handoff branch remains at `5ad33664f3312d3b973496d3e1e10b315bee031d`.
- `feature/person-ir-baseline` is 15 commits ahead of the handoff branch and contains the stacked work through PR #15.
- PR #2 and the PR #3–#15 chain diverged from the same handoff commit.
- PR #2 independently records a scoped **No-Go** for a new PersonIR source language/compiler.
- PR #15 now reaches the same practical conclusion from the stacked implementation: the existing core-Wasm capability host can express proposal/effect separation without a new language.
- PR #14 found a native-host intent reconstruction bypass, demonstrating that the graph verifier cannot secure incorrectly wired trusted-host code.

The two research lines therefore no longer disagree on the main decision. They still differ in implementation and evidence depth, so they should not be merged wholesale into one code path merely to eliminate branch divergence.

## Drift classification

| Area | Classification | Audit result |
| --- | --- | --- |
| Package review/install (#3) | No material drift | Directly advances the open plugin platform and package trust boundary. |
| Bounded core-Wasm runtime (#4) | No material drift | Correct conventional executable baseline and useful platform work. Keep the host ABI narrow. |
| Proposal/commit in production host (#5) | Acceptable mechanism, process drift | Useful for untrusted staged local mutation and stale-write protection. Treat as MVCC/CAS-style host mediation, not POP evidence. |
| Effect ledger (#6) | Acceptable mechanism, process drift | Useful outbox/idempotency/recovery boundary. Treat as conventional host safety infrastructure, not Effect-as-Data novelty evidence. |
| Review inbox (#7) | Highest product-framing drift risk | Keep only as a replaceable local reference/admin surface. LifeHub must not become an approval-workflow product. |
| PersonIR slices (#8–#14) | Correct as falsification experiments | They stayed under `experiments/person_ir` and exposed real limits. Do not promote them to the kernel. |
| Wasm baseline comparison (#15) | Correct convergence step | It satisfies the handoff decision gate sufficiently to defer compiler work. |
| PR #2 parallel experiment | Useful evidence, integration/process drift | Its conclusion is compatible with #15, but its implementation is a separate experimental line. Preserve evidence; do not merge both implementations wholesale. |

## Why #5–#7 were out of order

The handoff said not to move PersonIR hypotheses into the production kernel before they earned their place. PRs #5–#7 added proposal/commit, an effect ledger, and a review surface before the heterogeneous/hostile/baseline decision had completed.

That was a process error if those mechanisms are interpreted as implementation of POP.

It is **not automatically an architecture error** because the same mechanisms have an independent conventional-host justification:

- staged mutation prevents untrusted guest code from directly writing durable host state;
- base-version checks are ordinary stale-write protection;
- effect staging separates an untrusted request from host execution;
- durable effect status and uncertain-outcome handling are ordinary recovery/idempotency concerns;
- a local review surface is one possible operator interface for those host decisions.

The correction is to keep these mechanisms only on those conventional platform grounds. Their names and documentation must not imply that they validate PersonIR.

## PersonIR decision

The original decision gates required a meaningful semantic/enforcement advantage over a conventional capability runtime.

Current evidence does not meet that gate:

1. Five heterogeneous scenarios reuse the graph plumbing, but important semantics remain domain/host obligations.
2. Hostile tests expose a native-host binding flaw that the IR verifier cannot solve.
3. The conventional core-Wasm host already separates computation from durable writes and external effects.
4. PersonIR provides finer graph-level lineage and structural flow checks in its tiny closed operation set, but equivalent product value has not been shown to outweigh a new verifier/interpreter/language stack.
5. No representative performance or developer-productivity advantage has been demonstrated.

**Decision: No-Go for starting a PersonIR source language/compiler now.**

This is not a rejection of LifeHub. It is also not a proof that no future IR can be useful. The small graph/verifier may survive as an optional declarative workflow/policy/explanation format if later experiments justify it.

## Merge and retention guidance

### Keep as platform candidates

- #3 package approval/install
- #4 bounded core-Wasm runtime
- #5 staged local proposal/commit, after conventional-host reframing
- #6 effect ledger, after conventional-host reframing
- #7 local review UI only as a replaceable reference shell

These should be reviewed as ordinary LifeHub platform mechanisms. None should cite PersonIR/POP as the reason it belongs in Core.

### Keep as research evidence, not product architecture

- #8–#14 PersonIR experiment slices
- #15 baseline comparison and No-Go evidence
- PR #2's richer independent experimental evidence

Do not merge two divergent PersonIR implementations into production. Preserve the experiment history and extract only conclusions or independently useful host mechanisms.

## Immediate stop conditions

Until a new evidence gap is named, do **not**:

- start a PersonIR parser/source language/compiler;
- add new PersonIR node kinds to make scenarios pass;
- connect real email, payment, device, or other irreversible executors;
- make the review inbox the primary product model;
- hard-code life-domain concepts into the kernel;
- claim proposal/commit, effects, provenance, capability security, or Wasm sandboxing as LifeHub inventions.

## Next engineering order

1. Finish convergence documentation and stop expanding PersonIR.
2. Treat package installation + bounded Wasm as the current executable plugin foundation.
3. Harden the host/plugin binding exposed by the hostile test: host-owned immutable evaluation/request records, authenticated package/input snapshots, and sink-specific validation.
4. Keep proposal/effect services generic and independent of the review UI.
5. Move toward versioned plugin/service contracts and a typed component boundary (WIT/Component Model evaluation is reasonable, but not required to preserve the current No-Go decision).
6. Add provenance/policy instrumentation to the conventional host only where a concrete use case needs it.
7. Reopen PersonIR/compiler work only if a reproducible comparator demonstrates a capability the conventional host cannot reasonably provide.

## Product guardrail

LifeHub is not a calendar, dashboard, AcademicOS rewrite, AI assistant, or approval inbox.

> LifeHub does not define your digital life. It provides the mechanisms by which you assemble it.

The platform should remain open to unknown future extensions while preserving explicit authority, durable local state, mediated effects, and replaceable shells.

## Final audit judgment

**Direction correct; process temporarily disordered, now converging.**

There was a real process-level drift when research hypotheses were implemented in production-host modules before the falsification gate finished. There is not yet evidence of an irreversible architectural drift because `main` is unchanged, the work remains in draft stacked PRs, the PersonIR experiment stayed isolated, hostile tests found a real weakness, and the conventional baseline now produced the required No-Go decision for a new compiler.
