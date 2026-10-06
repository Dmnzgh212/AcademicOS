# LifeHub Engine foundation

LifeHub Engine is the shell-independent platform execution layer.

The v0.1 Web workspace remains a reference consumer. It is not the platform and
is not required for package discovery, component execution, services, storage or
capability enforcement.

## First engine boundary

The first engine slice introduces three concepts:

1. **Component** — an executable contribution owned by a package.
2. **Runner** — a trusted host adapter that knows how to execute one runtime.
3. **Execution lifecycle** — the engine starts/stops components and records their
   in-memory execution state.

A package may declare an explicit runner:

```toml
[[contributes]]
id = "worker"
point = "example.component"
runner = "vendor.runtime"
contract = "example.worker@1"
```

The extension point remains unrestricted. The runner is independent of the
extension point. This is intentional: a component is not a widget, page or
product-domain type.

Installing a package does **not** install or authorize a runner. Runners live on
the trusted host/platform side. The engine currently registers the existing
bounded core-Wasm runtime as `lifehub.wasm`; old v0.1 contributions whose
`entrypoint = "lifehub.wasm"` map to that runner for compatibility.

Shell-only contributions such as `lifehub.primitive` are not executable engine
components.

## Direction

The target architecture is:

```text
Shells / CLI / Desktop / Mobile
              |
        LifeHub Engine
   Component Manager / Lifecycle
       Runner Registry / IPC
              |
      +-------+--------+
      |                |
  Wasm runner      Person runner
  (existing)       (future PersonIR)
      |                |
     Wasm            PersonIR
```

This slice deliberately does not add a daemon, a new UI, a PersonIR syntax or a
new VM. Those should build on the engine boundary rather than define it.

The next engine slices should address persistent/background supervision, component
activation, engine IPC and runner isolation. A future PersonIR/LifeLang toolchain
should enter as another runner/backend path, not as Web-shell logic.


## Supervisor persistence

The second engine slice persists execution lifecycle separately from runner handles.
This distinction matters for a real platform process:

- an execution is recorded before a runner starts;
- terminal states survive process restart;
- a previously `running` execution is marked `interrupted` when a new engine
  instance opens the same store;
- the engine never pretends that an in-memory runner handle survived a crash;
- arbitrary runner result objects are intentionally not serialized into the ledger.

This is the first step toward a persistent supervisor/daemon. It is not yet a
background service manager: restart policy, activation policy and inter-process
control belong in later slices.


## Local control plane

The third engine slice adds a local non-HTTP control protocol for future Desktop,
CLI and other shells.

Protocol: `lifehub.engine-control@1`.

Current operations are intentionally small:

- `ping`
- `components`
- `executions`
- `start`
- `stop`

The transport uses authenticated local IPC through Python's multiprocessing
connection layer. Payloads are bounded JSON bytes using the same finite/depth/byte
validation as other LifeHub messages. Python pickle send/recv APIs are not used.

On Unix-like systems the intended transport is AF_UNIX. On Windows the intended
transport is AF_PIPE. HTTP and the reference Web workspace are not part of this
control boundary.

Runner-specific result objects are not exposed through the control protocol.
Shells receive component metadata and lifecycle state only.
