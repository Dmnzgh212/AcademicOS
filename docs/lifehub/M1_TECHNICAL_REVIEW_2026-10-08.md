# M1 technical review after LH-D-LOCAL-002

Date: 2026-10-08. Scope: engineering review of PR #61/#65, not acceptance or merge authorization.
Reviewed checkout: `af1f6caf49732ae0107266b5274935e1cdfa016b`.
Controlling direction: [LH-D-LOCAL-002](https://github.com/Dmnzgh212/AcademicOS/blob/docs/lifehub-supreme-direction-reaffirmed/docs/lifehub/LOCALIZATION_AND_USER_ACCEPTANCE_DIRECTIVE.md).
Revised gate lives on PR #56; operator/docs correction on PR #66 must be reconciled before integration.

## Evidence checked

Read Engine lifecycle, background parent/worker, recovery policy and reconciliation,
reference recovery script, energy integration script, selected security test assertions,
workflow and archive builder. Retrieved all three job logs from
[CI 384](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37730269391).
This is a scoped AI engineering review, not independent human audit, exhaustive security certification,
or a fresh local execution. Local scratch Python has no pytest; no local test result is claimed.

| Environment / job | Log result | Installed-wheel behavior |
| --- | --- | --- |
| Linux Python 3.11 / 113157560305 | 324 passed, 2 Windows-only skips | Guest work, process death/restart, Engine restart, route revoke, uninstall/reinstall passed |
| Linux Python 3.12 / 113157560034 | 324 passed, 2 Windows-only skips | Same proofs, retained-evidence check passed |
| Windows Python 3.12 / 113157560297 | 49 selected boundary tests passed | Real AF_PIPE proofs, recovery and energy modules passed |

Energy remaining changed 200 → 144 on both Linux jobs, 193 → 137 on Windows,
during a disconnected 0.85-second interval. This is synthetic guest-owned state,
not a real energy sensor or useful end-user energy product.
Actual guest kills produced new execution IDs. Actual Engine termination/new process
restored desired state without a new start command and retained route revocation.
Reference recovery additionally observed old-worker exit by replacement readiness
with Linux pidfd / Windows process handle; this does not prove zero transient overlap.

## Gate assessment

| Gate | Assessment under revised scope | Remaining qualification |
| --- | --- | --- |
| M1.1 separate non-Core modules and Shell-free work | Engineering evidence demonstrated: separately packaged energy meter/budget and reference provider/consumer | Same AI/team authorship is permitted. No external-human requirement remains. |
| M1.2 bounded guest recovery and failure isolation | Behavior demonstrated by actual kills, retry/quarantine and callable unaffected provider | Process death only; no general live-stall detector |
| M1.3 Engine recovery | Behavior demonstrated; historical interruption, new IDs and retained revoke checked across proofs/tests | No durable guest-memory recovery; exit observation has stated scope |
| M1.4 lifecycle and isolation | Stop/backoff, stale execution, reinstall invalidation, monitor failure and cleanup tests exist and passed | Aggregate resource risk requires explicit disposition below |
| M1.5 live controlled module calls | Host-bound route/package/execution identity; revoke/tamper/snapshot checks covered | Synchronous dispatch cannot process concurrent operator revoke mid-request |
| M1.6 installed deliverables | Linux/Windows installed-wheel proof and retained package/log metadata demonstrated | Artifacts were not downloaded and rehashed in this review; consistency checker is not attestation |

## Findings and risk disposition proposal

1. **Availability boundary is narrower than authority boundary.**
   Worker enforces Wasm linear-memory/module/fuel/message limits, rejects unavailable imports,
   and uses no WASI. Parent readiness/response receive deadline is three seconds;
   stop escalates terminate to kill. These do not cap total worker count, aggregate memory,
   native compiler memory, OS CPU consumption, or compilation wall time across the platform.
   Continuous finite ticks can still consume resources. Fuel is not an OS CPU quota.
   Proposal: eligible only for a bounded developer Alpha with reviewed local modules,
   synthetic data and a small manually controlled module set; no unreviewed-code or
   unattended general deployment safety claim. This is a review recommendation, not approval.
   A broad consumer release would require a separate availability decision based on actual use.

2. **Revoke means the next mediated access / checked output after a processed revoke.**
   Route resolution checks before and after provider calls bind host snapshots.
   The control server and lifecycle lock serialize work; queued revoke is not executed while
   a call holds dispatch. A re-entrant test that revokes inside a provider proves the
   post-output check, not concurrent second-client interruption. Keep this limit explicit.

3. **The energy proof alone does not prove OS cleanup.**
   Its uninstall assertion checks FAILED/not-ready ledger state after a delay.
   Its Engine-restart assertion does not pin/check the old process. Those stronger conclusions
   currently depend on reference recovery and background cleanup tests in the same workflow.
   Do not describe each energy assertion as a separate OS-level observation.
   Suggested next evidence-only improvement: observe its workers directly at uninstall
   and Engine restart, without changing Core.

4. **The developer archive is not a complete M1 reproduction bundle.**
   `scripts/build_lifehub_examples.py` includes `examples/lifehub` and the basic wheel smoke,
   not background/energy proof source. CI retains generated .lhpkg archives and logs, while
   source reproduction requires the exact checkout. This is a delivery/DX gap, not a demonstrated
   runtime security bug. Before offering a standalone M1 kit, bundle the matching proof sources,
   manifest/WAT inputs, commands and version identities. Do not call current archive a one-click product.

5. **No new reproduced Core vulnerability was established in this scoped review.**
   This does not exclude latent defects. Do not expand Core to resolve documentation/evidence gaps.
   Existing trusted local operator, filesystem races, no complete SSRF sandbox and other Alpha
   limitations remain as documented. Artifact uploads explicitly exclude authkey/database;
   this review does not claim a comprehensive secret scan.

## Next work and decision

First strengthen evidence/packaging in the example/tool layer, then reconcile #56/#62/#66
with this exact code/CI baseline and perform integration review of the stacked changes.
M1 technical approval and merges remain separate explicit decisions.
No author-recruitment blocker, user SDK exam, Core feature expansion or compiler work is required.
After this review closes, select one lawful upstream application function for local adaptation,
with provenance/license/update path and a simple import/run/revoke/error workflow.


## Follow-up code review: recovery ledger failure

A reproducible lifecycle defect was found after the initial scoped review:
reconcile inserted a RUNNING replacement execution before entering its try/except.
If execution persistence or the following desired-state update raised an SQLite
OperationalError, a handleless RUNNING item survived. A later shutdown attempted
handle.stop() on None. This is a truthful-lifecycle/cleanup defect, not a reproduced
capability bypass or authority leak.

The follow-up moves both ledger operations inside the existing failed-attempt
handling. Injected execution-insert and desired-update failures must leave a
FAILED/not-ready attempt in memory and persisted history; a subsequent reconciliation
starts a new ready execution, and shutdown succeeds. Tests use real installed Wasm
packages and a real killed worker with deterministic DB-operation fault injection;
they do not claim OS disk-full or actual SQLite-lock stress coverage.

The old implementation failed the desired-update regression with RUNNING instead
of FAILED and a shutdown AttributeError. Follow-up validation: the initial focused
lifecycle/snapshot/lease/evidence/startup suite passed 45 tests; both parametrized
ledger cases then passed; Ruff passed. Matching full Linux/Windows installed-wheel
CI is required for this runtime follow-up; prior CI 392 alone does not validate it.
No new feature, permission, recovery policy, Core domain logic or acceptance decision.
