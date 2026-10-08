# M1 evidence audit — not acceptance

Status: **M1 NOT ACCEPTED**. This is a working audit against
`docs/lifehub/M1_ACCEPTANCE.md` on `docs/lifehub-m1-acceptance-gate`, not
permission to merge the stacked runtime drafts.

Verified baseline: PR #58, commit `9b3d47719848a6d97839c7a2b7d461e190b462de`,
[CI run 365](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37705519626).
Linux Python 3.11/3.12 each passed 311 tests (2 Windows tests skipped);
Windows Python 3.12 passed 36 selected boundary tests. Real installed-wheel
recovery scripts passed on both AF_UNIX and AF_PIPE.

| Gate | Current evidence | Assessment |
| --- | --- | --- |
| M1.1 | Separately packaged heartbeat Wasm provider and observer Wasm consumer; shell-free guest counter advances. Both examples were implemented within this development effort. | NOT VERIFIED: independent authorship by someone other than the Engine author is not established. |
| M1.2 | Actual worker kill, autonomous new execution, two-retry crash-loop quarantine; another provider remains callable. Prior process-death script records failure before a client query. | Behavioral checks PASS; only process death is monitored, not live stalls. |
| M1.3 | Actual Engine termination, new manager automatically restores approved desired state, old history interrupted, new IDs, retained revoke; lease tests reject simultaneous owners. | Recovery checks PASS; an explicit cross-platform old-worker/orphan termination observation still needs to be included in the consolidated proof. |
| M1.4 | Uninstall without calls, reinstall invalidation, stop cancellation, multi-worker cleanup and lease release after injected errors, observable fail-closed supervisor health. | Covered by separate scripts/tests; consolidate evidence. Missing aggregate worker/memory ceilings are documented. |
| M1.5 | Guest observer invokes a live ready provider through host-resolved route; package and execution binding; revoke, tamper and stale-handle rejection. | Checks PASS. Synchronous control dispatch cannot process a second-client revoke during an active request. |
| M1.6 | Installed wheels and real daemon proofs passed on Windows/Linux. | Evidence retention added in this follow-up; artifact upload must pass CI before claiming availability. |

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

Observe the old guest's termination after actual Engine death on each platform,
then consolidate exact packages, logs, commit/PR map and every mandatory gate.
Do not invent a percentage of M1 completion or treat green CI as acceptance.

No guest-memory persistence, stalled-guest recovery, aggregate worker ceiling,
OS process memory/CPU quota, complete compilation wall-time budget, or concurrent
control dispatch is claimed. PersonIR and the WIT spike remain isolated research.
