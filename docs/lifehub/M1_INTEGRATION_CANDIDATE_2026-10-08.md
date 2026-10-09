> **Runtime follow-up:** PR #70 at 86771a2ed4f6e79c165d396925d5b3f9fa0cc07a fixes the recovery-ledger failure found after this candidate. [CI 393](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37863013423) passed Linux 3.11/3.12 (326 tests each, 2 Windows skips) and Windows 3.12 (51 boundary tests), including installed-wheel proofs. Integration must include that fix; CI 392 alone is no longer the recommended runtime head. No acceptance or merge is implied.

# M1 integration candidate — 2026-10-08

Status: **review-ready technical candidate; M1 NOT ACCEPTED; main unchanged**.
This candidate consolidates the revised gate and direction with the tested Engine stack.
It grants no merge permission and is not a consumer product release.

## Exact inputs

| Input | Pinned revision | Role |
| --- | --- | --- |
| #68 | dd7e9973048184d4ec43fe51d877b92d698708c1 | Runtime/example/tool baseline; CI 391 |
| #56 | fc61973837d7108984d479568353b5a7c23c1c6d | Revised M1 technical criteria |
| #62 | 2d28c5bf304456f66aac0e32147118b6d9e0c638 | LOCAL-002 controlling direction; earlier reuse guidance explicitly subordinate |
| #66 | 25b82b1a118197e34a5bc652434af5077f964759 | Engineering guide, nondeveloper operator goal and corrected audit |

Local integration merges of these inputs had no conflicts. Comparison against #68 shows
no changes in src, tests, examples, scripts or workflow. New candidate changes are documents.
The exact candidate checkout gets its own CI; CI 391 remains proof for its unchanged code baseline.

## Technical findings and proposed disposition

These are engineering assessments, not owner approval. PASS refers to observed bounded
behavior in the cited proof/test scope. Missing mechanisms stay missing.

| Gate | Assessment | Evidence and qualification |
| --- | --- | --- |
| M1.1 | PASS in engineering scope | Separate energy meter/budget packages; real persistent guest state changes while clients disconnected; no app-specific Core edits; AI provenance disclosed |
| M1.2 | PASS for process-death recovery | Actual guest kills, new IDs, finite retry/window/backoff/quarantine; unaffected provider stays callable; no general live-stall monitoring claim |
| M1.3 | PASS for tested restart behavior | Actual Engine termination/new process, automatic desired-state restoration, interrupted history, retained revoke; old worker exited by replacement readiness, not zero-overlap guarantee |
| M1.4 | PASS for tested lifecycle; risk disposition pending | Stop/backoff/stale stop, uninstall/reinstall, cleanup errors, lease and fail-closed supervisor tested. #68 energy additionally observes OS exit before next Engine request. Missing aggregate resources explicitly listed below |
| M1.5 | PASS for mediated contract scope | Host-owned caller/provider snapshots and execution binding; pregrant denial, revoke, stale/tampered package checks; synchronous dispatch limitation retained |
| M1.6 | PASS for tested OS/Python matrix | Installed wheels, standalone package archives and extracted source kits on Linux 3.11/3.12 and Windows 3.12; metadata, package hashes, logs, wheel retained |

[Technical review](M1_TECHNICAL_REVIEW_2026-10-08.md) contains the original scoped review.
Its energy OS-observation and standalone proof-source gaps were addressed by #68 and CI 391;
its resource and concurrent-dispatch qualifications remain current.

## Evidence index and reproduction

[CI 391](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37827785123)
at #68 revision above succeeded on all three jobs.
Linux 3.11/3.12 each passed 324 tests with two Windows-only skips; Windows passed
49 targeted boundary tests. Workflow invokes proof scripts from an extracted source archive
using a newly installed wheel and isolated Python imports.

Artifacts observed available/non-expired after that run:

| Artifact | ID |
| --- | --- |
| independent-energy-linux-python-3.11 | 11572770207 |
| independent-energy-linux-python-3.12 | 11571229675 |
| independent-energy-windows-python-3.12 | 11572277429 |
| recovery-linux-python-3.11 | 11571498247 |
| recovery-linux-python-3.12 | 11571797781 |
| recovery-windows-python-3.12 | 11571513850 |

Each artifact upload includes the matching wheel and source kit alongside allowlisted
package/evidence/log files. IDs can expire; use the Actions run, not an assumed permanent URL.
This review checked job logs and artifact metadata, not downloaded artifact byte hashes.
SOURCE_MANIFEST.json records source revision/per-file hashes; consistency checking is not attestation.

Engineering reproduction: install the matching wheel plus Wasmtime 36 in a disposable environment,
extract lifehub-engine-examples.zip, follow its README, and run:
- `python -I examples/lifehub-background-apps/run_demo.py`
- `python -I examples/lifehub-background-apps/run_recovery.py --output /fresh/path/recovery`
- `python -I examples/lifehub-external-energy/independent_proof.py --output /fresh/path/energy`

Set GITHUB_SHA to the exact source revision for retained recovery metadata.
Use fresh synthetic storage only. These fault-injection scripts approve their synthetic
packages; they are engineering tools, not ordinary user acceptance instructions.
Linux process observation requires pidfd support. No authkey/database belongs in published evidence.

## Residual risks — proposed bounded Alpha treatment

- No aggregate worker count/memory ceiling, OS CPU/RSS quota or complete compiler wall-time budget.
  Wasm fuel/linear-memory/module/message limits do not provide those ceilings.
- No general live-stall detector; process death and per-call deadline are the demonstrated mechanisms.
- Synchronous control dispatch cannot process a queued second-client revoke mid-call.
  Revoke applies when processed and on subsequent mediated checks; no instantaneous cutoff claim.
- No durable guest-memory restoration, zero transient restart overlap, general hostile-native sandbox,
  multiuser/remote operator identity boundary or cross-platform certification beyond the tested matrix.
- Current modules are synthetic engineering exercises. A useful localized open-source application
  and easy user-facing installation/error workflow remain the next delivery goal.

Proposal: restrict this milestone to a trusted-local-operator developer Alpha with reviewed modules,
synthetic data and a small controlled module set. The missing aggregate availability guarantees
remain a deployment limitation requiring explicit assessment; this document does not approve them.
Do not expand Core simply to make a status table look complete.

## Integration and next handoff

1. Review the runtime stack against the pinned gate, using the consolidated evidence and residual risks.
   Individual code review requirements are not replaced by this docs merge or CI.
2. Record an explicit M1 decision and separately approve the desired merge plan.
   Original PRs remain open/Draft until that plan is authorized; do not merge all automatically.
3. Keep #51 WIT and #63/#64 PersonIR/provenance research out of production dependencies.
   Presence of isolated research history is not acceptance of a compiler or new authority mechanism.
4. After technical disposition, choose one useful upstream application function, preserve license,
   source/version/update responsibility, and adapt it as a replaceable local module.
   Deliver import/run/permission-revoke/stop/error reporting to the user, not SDK or security homework.

No external-human-author recruitment is required. Ordinary users do not own engineering validation.

