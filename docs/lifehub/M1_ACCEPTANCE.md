# LifeHub M1 — Background Supervisor Acceptance Gate

**Status:** acceptance criteria agreed; **M1 NOT accepted**.
**Purpose:** one canonical engineering milestone, independent of PR count or green-test count.
**Authority:** these criteria formalize the agreed LifeHub M1 development checkpoint; this document alone does not approve any implementation or authorize merging unreviewed runtime PRs.

## Product claim to demonstrate

> On Windows and Linux, someone other than the Engine author can package and install a headless third-party background application. LifeHub Engine can run and supervise that application **without any Web/Desktop/CLI Shell remaining connected**, mediate its communication with a second independently packaged application, enforce revocation, and recover safely from guest and Engine failures. Adding the application must not require edits to Engine Core.

A persistent **Engine daemon** is not proof of a persistent **guest**. A one-shot Wasm invocation is not a background application. CI passing is supporting evidence, not the product result.

## Required M1 gates (all mandatory)

### M1.1 — Independent packages and genuine background work
- Two separately authored, reviewable, installable `.lhpkg` applications; no test-only synthetic host Python runner, trusted ad hoc runner registration or Web Shell dependency.
- The provider is a **persistent guest execution instance**, not merely a persistent daemon process. Host-owned, identifiable execution identity, observable readiness and terminal lifecycle.
- With all Shells disconnected for an explicit interval, prove that the **guest itself** performed at least two additional observable work turns or state transitions. Do not fake this with Engine-owned bookkeeping or a daemon-only timer.
- Add a third unrelated package using the same public component/runner contract **without modifying Core** as an extensibility check (it may be a small example, not a third large product).

### M1.2 — Safe unattended guest failure recovery
- Engine detects **actual guest process death** without waiting for a client query. State/ready transition and durable execution history are coherent.
- Under a documented opt-in/declared recovery policy, Engine automatically starts an eligible replacement guest **without operator interaction**. Replacement must have a new execution identity; no reuse of dead handles.
- Retry limits, failure-window accounting, bounded backoff, and a stop/quarantine state prevent a crash loop. Demonstrate both a recoverable crash and a repeatedly crashing component.
- A failed component must not block other independently installed components.
- Distinguish guest death, guest stall, fuel trap and planned stop. Do not claim stalled-guest recovery if only process-death monitoring exists.

### M1.3 — Engine process restart and persistent desired state
- Persist which approved components are *intended* to run (including relevant opt-in restart policy), **separately** from historical execution rows.
- Kill the actual Engine process (not only a graceful `shutdown()`), start a new Engine process, and demonstrate recovery of eligible intended background components **without operator calling `start` again**.
- Historic `running` rows are reconciled as interrupted; new executions receive new IDs. Revoked permissions remain revoked. Never represent in-memory Wasm state as durable unless explicit state persistence exists and has been tested.
- If the previous Engine/guest did not terminate cleanly, avoid duplicate managers and orphan guests; retain the single-manager DB ownership guarantee.

### M1.4 — Lifecycle, installation lifetime, and cleanup
- `start`, `ready`, `stop`, `failed`, `interrupted`, `recovering` (where applicable) have documented, tested transitions and truthful status reporting.
- Explicit stop must suppress automatic restart; uninstall/package replacement must invalidate and terminate its old live guest **without waiting for a call**, without restoring removed routes or stale execution authority.
- On shutdown, an exception stopping one worker must **not** skip other workers or prevent kernel/database lock release; aggregate/report cleanup errors. A fresh Engine manager can acquire the DB afterward.
- Monitor failure cannot silently disable all future failure detection; make monitor health/failure observable and use a bounded recovery or fail-closed policy.
- Enforce finite process/module/CPU/memory/IO/start/stop budgets or document precisely which resource ceilings are missing; no guest ambient OS permission by default.

### M1.5 — Real authorized application-to-application IPC
- Two independent packages communicate via a declared interface resolved to a **live, ready provider**, not a test callback or operator pretending to be a guest.
- Caller identity and provider selection derive from the trusted host execution, **not JSON fields supplied by a guest**. Never hand the Engine control authkey to untrusted guests.
- Routes remain bound to approved package snapshots and (for live services) provider execution identity. Uninstall/reinstall and provider restart cannot refresh an old invocation's authority.
- Revocation blocks the next authorized operation and prevents releasing a response when revocation is processed during a call. Document **control-plane concurrency semantics**; if real concurrent revocation cannot be processed while a request is in flight, do not claim instantaneous mid-flight cut-off.
- Resource-bounded JSON and existing Wasm sandbox/authority rules must remain enforced.

### M1.6 — Cross-platform, installed-artifact proof
- Use actual built/installed wheels and standalone package archives; do not rely solely on editable-checkout imports or hand-wired test fixtures.
- Run separate real Engine processes on **Windows with AF_PIPE** and on **Linux with AF_UNIX**. No browser/HTTP Shell is required.
- Demonstrate M1.1–M1.5 end to end: install → start → disconnect all clients → observe guest activity → call through approved route → revoke → deny → guest crash/automatic recovery → crash-loop limit → Engine process death/restart/automatic desired-state restoration → uninstall/stop and cleanup.
- Preserve command/script, git SHA, package SHA256 identities, platform/Python versions, execution IDs, observed timings and raw CI logs so someone else can reproduce the result.

## Out of scope for M1

- PersonIR, LifeLang, compiler productionization, broad WIT/Component Model adoption, full desktop/mobile/Web application or dashboard.
- Arbitrary third-party Python/native execution inside the trusted Engine, or broad filesystem/network/WASI privileges.
- Claiming a generally secure hostile-native-code OS sandbox, a Windows service installer, or durable guest-memory restoration without separate evidence.
- Broad feature expansion solely to increase test count.

Maintain the isolated WIT experiment as research; do not merge it into runtime to satisfy M1 by fiat.

## Report/merge protocol

1. **During development:** team may work continuously and independently, without a review request on every PR. Immediate escalation only for material security failures, user-data-loss risk, architecture reversal, or blocked decisions.
2. **At M1 completion:** submit one consolidated evidence bundle with the exact runnable third-party packages; installed-wheel demo; Linux and Windows logs; relevant PR/commit map; known limitations; and a gate-by-gate PASS/FAIL/NOT VERIFIED table.
3. **Assessment:** tests and CI support evidence, but cannot replace real behavioral proof. Do not state M1 completed when any mandatory gate is missing.
4. **Merging:** PRs remain Draft until their individual code reviews and CI gates are satisfied; M1 acceptance is a separate explicit decision and is **not** implied by this document or by a green CI badge.

## Existing baseline (not a new M1 pass)

- PR #52: independent packaged headless one-shot Wasm apps, real daemon, grant/revoke, installed-wheel proof; **not** persistent guest.
- PR #53: persistent Wasm guest and live authorized interface, Shell-free work; **not** unattended auto-restart.
- PR #54: independent process-death monitoring while Shell-free; **not** unattended guest restart.
- PR #55: installation lifetime work in progress; judge actual outcomes by merged evidence and review, not PR title.

**Next report trigger:** all mandatory M1 gates met, or an architecture/security blocker requiring a decision. Routine PR-by-PR status pings are not required.
