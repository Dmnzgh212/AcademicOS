# M1 evidence audit — not acceptance

Status: **M1 NOT ACCEPTED**. This is a working audit against
`docs/lifehub/M1_ACCEPTANCE.md` on `docs/lifehub-m1-acceptance-gate`, not
permission to merge the stacked runtime drafts.

Verified runtime baseline: PR #61, commit `ff74cc2f2e0d9c256ee5c88e8a4ecca17ac49b6e`,
[CI run 370](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37709612021).
Linux Python 3.11/3.12 each passed 315 tests (2 Windows tests skipped);
Windows Python 3.12 passed 40 selected boundary tests. Real installed-wheel
recovery scripts passed on both AF_UNIX and AF_PIPE.

| Gate | Current evidence | Assessment |
| --- | --- | --- |
| M1.1 | Separately packaged heartbeat Wasm provider and observer Wasm consumer; shell-free guest counter advances. Both examples were implemented within this development effort. | NOT VERIFIED: independent authorship by someone other than the Engine author is not established. |
| M1.2 | Actual worker kill, autonomous new execution, two-retry crash-loop quarantine; another provider remains callable. Prior process-death script records failure before a client query. | Behavioral checks PASS; only process death is monitored, not live stalls. |
| M1.3 | Actual Engine termination, new manager automatically restores approved desired state, old history interrupted, new IDs, retained revoke; lease tests reject simultaneous owners. | Recovery checks PASS; old-worker exit by replacement readiness verified on both platforms in CI run 367. |
| M1.4 | Uninstall without calls, reinstall invalidation, stop cancellation, multi-worker cleanup and lease release after injected errors, observable fail-closed supervisor health. | Covered by separate scripts/tests; consolidate evidence. Missing aggregate worker/memory ceilings are documented. |
| M1.5 | Guest observer invokes a live ready provider through host-resolved route; package and execution binding; revoke, tamper and stale-handle rejection. | Checks PASS. Synchronous control dispatch cannot process a second-client revoke during an active request. |
| M1.6 | Installed wheels and real daemon proofs passed on Windows/Linux. | Evidence retention PASS in CI run 366: Windows 3.12 and Linux 3.11/3.12 artifacts uploaded. |

## Reproduction and retained artifacts

Use an installed wheel with `wasmtime>=36,<37`, outside the source import path:

```sh
python -I examples/lifehub-background-apps/run_demo.py
python -I examples/lifehub-background-apps/run_recovery.py --output /fresh/path/recovery
```

`--output` requires a new directory and preserves the exact `.lhpkg` bytes,
SHA256 identities, git SHA supplied by `GITHUB_SHA`, Python/platform, elapsed
wall time, execution IDs and daemon log. A failed run retains a NOT COMPLETED
metadata record if package installation completed. CI also preserves stdout
and the wheel. The upload allowlist excludes the operator authkey and database;
never publish the whole working directory as an artifact.

Raw workflow/job logs remain attached to the linked GitHub Actions run. The
recovery script uses a 0.6-second shell-free work interval, a 1-second disconnected
post-kill interval, and bounded polling (10-second timeout, 50-ms intervals).
These are observed test conditions, not real-time platform guarantees.

## Remaining decisions and limits

A genuine independent integrator must package and exercise applications through
public contracts without app-specific Core edits. Existing examples demonstrate
mechanics and cannot establish that external developer result by themselves.

The recovery proof now pins the old process with a Linux pidfd or Windows
SYNCHRONIZE handle before Engine termination, starts a replacement manager,
and requires the old process to be terminated by replacement readiness. This
observes absence of a live orphan at that point, not a zero-overlap guarantee
throughout startup or OS reaping of zombie entries. Linux proof requires pidfd
support (Linux 5.3+); this is a proof-tool requirement, not a runtime dependency.
Both platform jobs passed in CI run 367. The proof does not establish
zero transient overlap during restart. Independent integration remains open.
Do not invent a percentage of M1 completion or treat green CI as acceptance.

No guest-memory persistence, stalled-guest recovery, aggregate worker ceiling,
OS process memory/CPU quota, complete compilation wall-time budget, or concurrent
control dispatch is claimed. PersonIR and the WIT spike remain isolated research.

Evidence-retention run: [CI 366](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37706653263), commit `ab6860258cd1e6915d1beeede15a6559fb122087`.

## Delivery index and revision map

- [Canonical M1 criteria](https://github.com/Dmnzgh212/AcademicOS/blob/docs/lifehub-m1-acceptance-gate/docs/lifehub/M1_ACCEPTANCE.md): agreed gate; acceptance remains a separate decision.
- [Independent integrator guide](INDEPENDENT_INTEGRATOR_GUIDE.md): installed-wheel commands, manifests, ABI and honest evidence requirements.
- [Background runner/reference proof](../../examples/lifehub-background-apps/README.md): public boundaries and lifecycle.
- [Recovery proof](../../examples/lifehub-background-apps/run_recovery.py): actual process kills and retained artifact metadata.

| Draft PR | Scope | Evidence baseline |
| --- | --- | --- |
| #44–#50 | Route lifetime, resilient control, guest interface calls, readiness/cleanup, lease and Windows transport | Pre-background security/transport foundation; retain individual PR review requirements. |
| #51 | Isolated WIT research | Not a runtime dependency or M1 gate shortcut. |
| #52 | Independently packaged one-shot apps | Packaging and IPC baseline; not independently authored external integration evidence. |
| #53–#55 | Persistent guest, unattended monitor, uninstall/reinstall lifetime | Real installed-wheel background proof and matching lifecycle tests. |
| #57 | Fail-closed monitor health and unconditional cleanup | CI 364. |
| #58 | Bounded automatic guest recovery and persistent desired state | Commit `9b3d47719848a6d97839c7a2b7d461e190b462de`, CI 365. |
| #59 | Retained packages/logs and old-worker exit observation | Commit `7ef4ec4308497bb14cc57576b43f17d3b6a66069`, [CI 367](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37707048863). |
| #60 | Independent integration guide | Commit `e846e65d747c609c11a9ba06b11c4a4340047b1e`, [CI 368](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37707525023), success. |

CI 367 contains three downloadable recovery artifacts: Linux Python 3.11,
Linux Python 3.12 and Windows Python 3.12. Each includes exact package archives,
wheel, structured evidence, proof stdout and Engine log. The metadata's git SHA
identifies the actual Actions checkout; the table identifies the source PR head.
No operator authkey or personal database is included. Raw job logs remain in
Actions. Do not treat artifacts as a production release or merge authorization.

## Stop-at-death regression found during audit

When an opted-in guest had actually exited before its monitor reconciled state,
`stop-component` cancelled desired state but attempted `stop` on the stale
RUNNING row. `stop` reconciled it to FAILED and returned an error instead of the
component-level stopped result. The fix reconciles process death after intent
suppression and before selecting live executions. It does not grant authority
or erase FAILED history.

Regression checks cover stop immediately after actual guest death, uninstall
and identical reinstall before replacement, and rejection of a stop against an
old failed execution without cancelling the replacement's desired state. These
are lifecycle/security checks, not new Core features. Validation of this follow-up
must be reported separately from the already green CI 367/368 baselines.

Additional budget/cancellation checks: stop after the public desired state reports
RECOVERING and before its declared retry deadline; after that deadline no new
execution appears. Real guest death consumes one retry, successive manager
recreation retains failure-window history and consumes the remaining allowance,
and further recreation retains quarantine instead of resetting the budget.
The local budget test closes/recreates managers while preserving intent; it is
not described as repeated OS Engine kills. The separate installed-wheel proof
continues to exercise actual Engine process termination. No recovery mechanism
or authority boundary was expanded for these tests.

## Current handoff evidence (2026-10-07)

CI run 370 succeeded for Linux Python 3.11/3.12 and Windows boundaries. Its three
recovery artifacts were checked as available and not expired on 2026-10-07:
`recovery-linux-python-3.11` (11521730527), `recovery-linux-python-3.12`
(11521625316), `recovery-windows-python-3.12` (11521565981). Download through the
linked Actions run; retention may expire later. The integrator guide now targets
this tested revision, including the stop-at-death fix rather than an older wheel.

This supersedes the pending-validation wording in the regression section above:
stop/death, uninstall/reinstall, stale stop, backoff cancellation and persisted
retry-budget regressions passed in CI 370. Prior run references remain historical.
No newly authored external packages or independent integration report have been
received or verified. M1.1 remains NOT VERIFIED; full M1 is NOT ACCEPTED.

Isolated research #63/#64 and actual PROV serializer reuse do not satisfy M1.1 or
replace the installed Engine proof. They add no runtime dependency and should
not be included as product acceptance evidence. The next missing deliverable is
an independently authored provider/consumer integration with source/package
identities, no Core modifications, disconnected guest work, routed calls,
revocation, failure recovery and Windows/Linux evidence under the published gate.

## Windows proof startup failure discovered in follow-up CI

Run 37721889158 passed both Linux jobs but failed Windows one-shot app smoke:
the launcher observed the newly created auth-file before its contents were
written, and `load_authkey` correctly rejected the short key. The exception
escaped startup before the child handle reached the caller's cleanup block;
the surviving child held the temporary database open. This is a proof launcher
race/cleanup defect, not permission to weaken runtime key validation.

The proof launcher now polls unfinished key reads within its existing bounded
startup interval and closes its own child on every unsuccessful startup exit.
A failed control response is still an immediate error. Fault-injection checks
cover partial-key retry, permanently invalid-key timeout cleanup and rejected
ping cleanup; real Windows/Linux installed-wheel CI must validate the follow-up.
The failed Windows run uploaded only a wheel: artifact presence alone is not
proof that recovery ran or that an evidence bundle is complete. CI 370 remains
the last fully verified runtime handoff until the new run passes.


## Retained-evidence check

`python scripts/check_lifehub_recovery_evidence.py ROOT WHEEL PROOF_LOG CHECKOUT_SHA OUTPUT`
checks completed metadata, explicit checkout identity, distinct replacement IDs,
old-worker exit observation, exact package inventory/digests and nonempty logs/wheel.
CI runs it after recovery and preserves `validation.json`. Missing metadata,
NOT COMPLETED status, mismatched identity and changed package bytes fail. Failure
artifacts remain useful diagnostics but are not accepted as complete evidence.
This is local file consistency checking, not attestation: forged metadata/logs
can pass, wheel hash recording does not prove that wheel was installed, and
independent authorship and M1 acceptance remain unverified. No Core changes.


## Current pinned integration baseline

The guide now pins source `421542bba98036dfa8f35c78f8d72ddb92a28c43` and
[successful run 37723233133](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37723233133),
including proof startup cleanup and actual retained-evidence validation on all
three jobs. This supersedes CI 370 as the handoff target; older references above
remain historical. Recovery artifacts: Linux 3.11 11526642079, Linux 3.12
11526900858, Windows 3.12 11526268561; available/non-expired when checked
2026-10-07. The guide lists independent submission materials. No external
integration submission has been verified; M1 remains NOT ACCEPTED. Further
self-authored fixtures cannot establish independent authorship.
