# LifeHub platform recovery — 2026-10-05

LifeHub is an open personal computing platform. Package, capability mediation,
Wasm execution, generic interfaces and replaceable shells are the engineering priority.
PersonIR and a source language/compiler remain research directions with insufficient
current evidence to justify expansion.

## Verified recovery anchors

- main: `856b48a7adbb480d567d63c2582aa02d7405ce92`, unchanged.
- PR #16 audit: `0e53675fe5a3576afc8a075be65d789798a269dc`.
- Platform through PR #7: `dc65605c0e84dcf545a8f8fdd7be176eb9c2a982`.
- All PRs #1–#16 were open drafts at inspection; none merged.
- #1 → #3 → #4 → #5 → #6 → #7 form the platform stack.
- #8 → #9 → #10 → #11 → #12 → #13 → #14 → #15 → #16 continue
  from #7 with research and audit work. #2 is a divergent research implementation.

## Separation performed

`feature/lifehub-platform-contracts` starts at #7 and carries only the platform
mechanisms plus selected direction documents from #16. It has no
`experiments/person_ir` implementation or research test dependency. The original
branches and draft PRs retain all experiment evidence, including both independent
compiler No-Go findings. They have not been deleted, merged or retargeted.

Platform validation uses `python -m pytest -q` and
`python -m ruff check src tests examples/lifehub`. Research validation
belongs on its original branch, using explicit experiment paths. Do not merge the
whole #16 stack into main merely to obtain its direction documents.

## First resumed engineering slice

`LifeHub.catalog()` implements `lifehub.catalog@1`, a detached JSON discovery
contract for trusted local shells. It lists package identity, requested permissions,
and arbitrary extension contributions; it filters extension points without a fixed
list of domains. It exposes neither host filesystem paths nor personal records.
Reading it grants no authority and does not activate a plugin. Managed discovery
continues through the existing package approval verifier.

The catalog is an in-process interface, not an authenticated HTTP API or a WIT
Component Model implementation. CLI/web shells can adopt it incrementally. Existing
shells remain compatible.

## Original next slices (recovery-time plan)

The implemented follow-up slices and remaining gaps are recorded in
[PLATFORM_STATUS.md](PLATFORM_STATUS.md). The list below is the original recovery
plan, not a current backlog.

1. Migrate shell discovery to the catalog, keeping rendering outside Core.
2. Define contribution/service contract negotiation separately from package API
   and the existing core-Wasm host ABI; reject incompatible versions at use time.
3. Exercise package install → catalog → explicit Wasm activation → capability
   rejection with a domain-neutral sample package and two shell consumers.
4. Evaluate WIT/Component Model only against a concrete interoperability gap.

Proposal/commit and fake effect ledgers remain conventional host safety services.
The review inbox is a reference shell. No new calendar/payment/approval product,
real external executor, or compiler is part of this recovery.
