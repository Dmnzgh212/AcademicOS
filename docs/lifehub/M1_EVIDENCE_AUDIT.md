# M1 evidence audit — not acceptance

> **2026-10-08 acceptance scope correction (project owner):** the external-human-plugin-developer condition in earlier paragraphs below is superseded by [M1 revised gate PR #56](https://github.com/Dmnzgh212/AcademicOS/pull/56) and [LH-D-LOCAL-002](https://github.com/Dmnzgh212/AcademicOS/blob/docs/lifehub-supreme-direction-reaffirmed/docs/lifehub/LOCALIZATION_AND_USER_ACCEPTANCE_DIRECTIVE.md). M1 measures separately packaged **locally prepared/adapted** modules and technical/safety behavior. AI/Engine team may author them; no external human author required. User tests need only import/run/revoke/copy error when a user-facing delivery exists. The older "NOT VERIFIED" authorship judgment is historical, **not a remaining M1 technical blocker**. M1 is **still NOT ACCEPTED**, because code review, gate-by-gate technical assessment and explicit merge decision are pending.

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
| M1.1 | Separately packaged heartbeat provider/observer and distinct AI-authored energy provider/consumer in PR #65; guest-owned work observed with no Shell connected in CI #384. | **Engineering behavior demonstrated** under revised gate; external human authorship is no longer required. Pending final M1 gate review. |
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

Engineering integrators must be able to adapt, package and exercise local modules through controlled public contracts without app-specific Core edits. Existing examples and the distinct AI-authored PR #65 application exercise this technical property; **unrelated external-human authorship is no longer a M1 gate**. User-friendly import/run/revoke/error reporting is a separate usability delivery goal.

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
Historical as of this earlier baseline: no newly authored external packages had yet been checked. **Superseded by PR #65 / CI #384:** new AI-authored, separately packaged energy provider/consumer verified on Linux and Windows. External human authorship remains unverified but **is no longer mandatory for M1**. Full M1 remains NOT ACCEPTED pending revised technical/safety assessment and merge review.

Isolated research #63/#64 and actual PROV serializer reuse do not satisfy M1.1 or
replace the installed Engine proof. They add no runtime dependency and should
not be included as product acceptance evidence. Under the **old** gate, the next deliverable was an external developer integration. Under the **revised** gate, the next action is consolidate PR #61/#65 evidence and check each retained engineering/safety requirement, known limits and package/source identities before a separate technical-Alpha acceptance decision; **do not recruit an outside human plugin programmer solely to clear M1**.

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
2026-10-07. The guide lists independent submission materials. AI-authored PR #65 now contributes different-source engineering integration proof. It is **not** external-human evidence and need not be under the revised M1 gate. M1 remains NOT ACCEPTED until final technical/safety review. Additional self-authored fixtures should address genuine gaps rather than endlessly prove authorship.

## Revised M1 technical-gate evidence checkpoint (2026-10-08)

Project owner's scope revision replaces the historical requirement for a separate outside human program author with **locally adapted, separately packaged modules and concrete Engine tests**. It does **not** weaken sandbox, package review, default-deny routing, revocation, process recovery, safety/cleanup or artifact verification.

- [PR #61](https://github.com/Dmnzgh212/AcademicOS/pull/61), latest documented pre-revision runtime CI #383: cross-platform Engine tests and evidence checker run green; its Draft stack still requires integration review.
- [PR #65](https://github.com/Dmnzgh212/AcademicOS/pull/65), [CI #384](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37730269391): separate AI-authored synthetic-energy provider/consumer in two genuine packages, no app-specific Core modifications; Linux Python 3.11/3.12 each 324 tests passed (2 Windows-only skipped), Windows Python 3.12 49 targeted tests passed. New installed-wheel application integration verified: background work without Shell, mediated provider→consumer response, deny before grant, revoke/deny, actual guest death and autonomous restart, actual Engine death and desired-state restoration, stop/reinstall/revoke safety. Preserve identity labels: AI-generated exercise, not human certification.
- Remaining technical review: aggregate/OS worker resource limits and live-stall behavior, synchronous control dispatch semantics, package/transport/data boundaries, limits stated accurately; explicit PR review and gate assessment. Existing statements about absent CPU/memory quotas etc must not be silently marked PASS by changing the authorship rule.
- **Operator UX** is a separate engineering deliverable: [operator guide](LOCAL_MODULE_OPERATOR_GUIDE.md) says ordinary users should import, run, review/revoke rights, stop/uninstall and copy redacted errors, without writing modules or manually conducting security audits. Current M1's developer CLI is not claimed to be a one-click UI.

**Decision after review:** accepted technical Alpha, deferred risk with explicit scope, or not accepted. No author-count or outside-human recruitment criterion is applicable. Documents in separate Draft PRs are not automatically merged or accepted.
