# Persistent bounded background guest — first slice

`thirdparty.heartbeat` is an independently packaged Wasm guest. Its mutable
counter lives inside the persistent Wasm instance, not in a daemon timer or
execution metadata. The host schedules bounded `tick()` calls every 100 ms
when its private command queue is idle. A separate `thirdparty.observer`
Wasm package obtains the counter through an explicitly approved live interface.
Neither package adds Shell contributions or requires a Core edit to install.

```sh
python -m pip install -e '.[dev,wasm]'
python examples/lifehub-background-apps/run_demo.py
```

Keep the neighboring `lifehub-third-party-apps` directory: this proof shares
its public packaging/daemon utilities. The resulting `.lhpkg` files contain
only their own manifest and compiled guest, with no Python guest runner.

The demonstration launches a real separate Engine daemon, starts the background
guest, denies observer before grant, approves a digest-bound route, reads its
counter, disconnects all clients for 800 ms, and verifies at least two additional
guest increments. A separately packaged fault probe self-fails after three
guest turns: its failure timestamp must precede client reconnection by at least
50 ms, demonstrating active monitoring rather than query-time reconciliation.
The fault probe is a controlled failure test, not claimed as a third real app.
The proof revokes and verifies next invocation denial, terminates
the Engine process, then starts a new daemon. Old history must be interrupted,
revocation retained, and explicit guest restart assigned a new execution ID.
It finishes by stopping that guest through the public protocol.

## Runner boundary and lifecycle

The new host-installed `lifehub.wasm-background` runner accepts approved Wasm
only. Each live instance occupies a private Python host subprocess, uses no
WASI, and exposes only bounded `lifehub_service` JSON memory operations.
The guest has no pipe, process, authkey, filesystem or network API. The host
subprocess is trusted infrastructure, not an arbitrary Python guest.

The ABI requires exported memory and three `() -> i32` exports: `ready`
returns 1; `tick` and `run` return 0. `run` emits exactly one bounded JSON
response. Fuel is reset per mediated turn; memory/instance/table limits apply.
Parent request/start deadlines are three seconds; timeout kills the worker.
Stop terminates it, escalating to kill after one second. Parent pipe EOF
causes worker exit after its current fuel-bounded turn. No operator authkey
is passed through these pipes or module memory.

Installation approval time and digest/manifest are bound to the handle.
The monitor also checks the installed approval identity of each live worker.
Uninstall or replacement terminates that worker and records failed without a
subsequent guest call. The proof uses the public uninstall CLI while the daemon
is alive, disconnects again, checks pre-query failure, reinstalls identical bytes,
and verifies a new execution identity without resurrecting the revoked route.
This monitors installation records, not continuous hashing of filesystem assets;
tampered files still fail verification on mediated calls.
Routes are checked before call and before output release; a consumer invocation
also captures the provider execution ID, so a replacement live instance cannot
refresh an old invocation. Exactly one live instance per component is allowed.

**Restart policy: manual by default, bounded automatic recovery by explicit opt-in.**
`components.config.restart` requires `max_retries` (integer 1–5), `window`
(5–3600 seconds), `backoff` (0.1–30 seconds), and `max_backoff` (0.1–60
seconds, at least backoff). Starting an opted-in component persists approved
installation-bound desired state separately from execution history. Failures
consume a persisted rolling-window budget with capped exponential backoff;
exhaustion quarantines the component. Successful starts do not clear recent
failures; explicit operator start resets the budget. `desired-components` exposes
policy and status; `stop-component` also cancels a pending recovery.
Installation replacement or uninstall invalidates intent, including identical
reinstallation. Recovery never synthesizes grants or resumes guest memory.
`run_recovery.py` kills a real guest and then the actual Engine process, checks
new execution identities without operator start, and exercises crash-loop
quarantine, retained revocation, and explicit stop.
An Engine-owned monitor checks process death on a 100 ms interval without any
client. It records failed and clears readiness using its own ledger connection.
Lifecycle transitions serialize with the monitor; normal stop remains stopped.
If the ledger is busy, readiness clears and persistence retries after 500 ms.
`supervisor-health` on the public control protocol reports monitor failure.
Unexpected monitor termination clears guest readiness, terminates background
workers and rejects new background starts until a new Engine manager is created.
Cleanup attempts every worker, falls back to kill after a stop error, aggregates
errors, and releases the kernel and owner lease even when worker cleanup fails.
Intervals are targets, not real-time bounds; active control execution can delay
monitor access to the lifecycle lock. Engine restart marks previously running
history interrupted and restores only eligible opted-in intent. New start has a new ID;
revoked grants remain revoked. Explicit stop and planned shutdown suppress recovery. Storage-only close
also kills this runner's private workers while leaving interruption history.

## Remaining limitations

This is process-death monitoring, not a complete supervisor. It does not detect
a live-but-stalled guest until a bounded request is attempted. There is
no general boot activation, worker state persistence, nested
background calls, streams, cancellation or general SDK. Idle tick scheduling
can be delayed by sustained requests; it is not a real-time guarantee. OS process
isolation is for termination, not a hostile native-code sandbox. Compilation
inside the child has a parent deadline, but no claimed OS memory/CPU quota.
The six-digit demo counter wraps its displayed value; the tiny guest codec is
not a general JSON implementation. These limits must remain explicit when
assessing the full acceptance gate.

Recovery uses a supervisor-owned temporary kernel and SQLite connection;
invocation verification uses the operator thread's kernel after startup. No
SQLite connection is shared across these threads. Recovery policy uses wall-clock
timestamps and is not a trusted-clock guarantee. Control dispatch is synchronous:
a second client cannot revoke during an active request; authorization is checked
again before releasing output, but instantaneous concurrent revocation is not
claimed. Replacement startup holds the lifecycle lock and can delay other work.
There is currently no aggregate worker-count or process-memory ceiling, and
filesystem/compilation work is not fully wall-time bounded. These are explicit
M1 resource-bound limitations, not evidence of complete M1 acceptance.

Independent developers: see [the integration guide](../../docs/lifehub/INDEPENDENT_INTEGRATOR_GUIDE.md) for manifests, guest ABI, operator commands and evidence requirements. Reference example success does not establish independent authorship.
