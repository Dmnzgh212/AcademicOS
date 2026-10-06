# LifeHub focused platform review checkpoint — 2026-10-06

Scope: the resumed platform stack against PR #7 (`dc65605c0e84dcf545a8f8fdd7be176eb9c2a982`),
with PR #16 retained as the direction-audit recovery anchor. This checkpoint is
an implementation review and controlled test record, not independent acceptance,
a security certification, or authority to merge main.

## Findings resolved

| Boundary | Finding and resulting behavior | Evidence |
| --- | --- | --- |
| Service grant | A second review lookup could approve a different snapshot from the stored binding; compare approval with the exact persisted binding | #28; service revalidation tests |
| Capability handles | Old storage/egress handles could reuse old permissions after approved replacement; handles bind manifest and content digest | #28; replacements with narrowed and identical manifests |
| Network transport | urllib followed redirects beyond initial-URL authorization; automatic redirects disabled, separate requests reauthorize | #29; real local HTTP tests for 301/302/303/307/308 and 200 |
| Wasm submission | Old run output could acquire a replacement package digest; retain starting digest and reject changed approval before submission | #30; six lifecycle tests across proposal/effect paths |

Both Wasm replacement regression tests fail against the pre-fix code and pass
with the fix. Final checks and staged submission use the same SQLite write
transaction; filesystem writes are not part of that transaction.

## Boundaries checked without a new implementation finding

- Proposal approval checks stored plugin/digest, current approval and declared
  namespace; stale record bases prevent commit.
- Effect approval/dispatch checks package binding and allowed destination;
  uninstall invalidates pending/approved requests. The approved-then-tampered
  dispatch test confirms no fake delivery occurs.
- Fake effects retain at-most-one-attempt behavior and explicit unknown-outcome
  recovery. This says nothing about correctness of a future real executor.
- Platform paths and pytest dependencies omit `experiments/person_ir`; original
  research branches remain separate. No language/compiler implementation added.

## Validation and decision

221 local tests and Ruff pass. Runs 320/321 passed Python 3.11/3.12, installed-wheel
and reproducible examples companion smoke. The #30 runtime-fix revision is
`78b8259b76d8dd103d98d57b816bf7d112c0ed94`; run 322 passed for that revision.
Latest revision checks must pass before any integration decision.

The bounded developer prototype has executable Package/Capability/Runtime/service
and replaceable-shell examples. Samples distribution tooling exists. Independent
cumulative review, main integration and release publication remain outstanding.
Do not expand the prototype with a new language merely to fill these review gates.

Retained limits: trusted local operator APIs, no remote identity boundary,
filesystem/database races not fully excluded, no DNS pinning or complete SSRF
sandbox, compilation time not fuel-bounded, row-bounded records without total byte
limits, reference layout storage in LifeStore, and no real external executor,
Mesh, WIT Component Model or accepted PersonIR compiler.
