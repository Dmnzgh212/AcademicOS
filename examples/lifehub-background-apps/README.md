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
counter, disconnects all clients for 600 ms, and verifies at least two additional
guest increments. It revokes and verifies next invocation denial, terminates
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
Routes are checked before call and before output release; a consumer invocation
also captures the provider execution ID, so a replacement live instance cannot
refresh an old invocation. Exactly one live instance per component is allowed.

**Restart policy: explicit operator restart only, zero automatic retries.**
Guest death is detected on the next Engine execution query or interface access,
then recorded failed and not ready. Engine restart marks previously running
history interrupted and starts no guest automatically. New start has a new ID;
revoked grants remain revoked. Explicit stop records stopped. Storage-only close
also kills this runner's private workers while leaving interruption history.

## Remaining limitations

This is not a complete continuously monitored supervisor. Death history is
reconciled on Engine access, not immediately by a background monitor. There is
no automatic restart/backoff, boot activation, worker state persistence, nested
background calls, streams, cancellation or general SDK. Idle tick scheduling
can be delayed by sustained requests; it is not a real-time guarantee. OS process
isolation is for termination, not a hostile native-code sandbox. Compilation
inside the child has a parent deadline, but no claimed OS memory/CPU quota.
The six-digit demo counter wraps its displayed value; the tiny guest codec is
not a general JSON implementation. These limits must remain explicit when
assessing the full acceptance gate.
