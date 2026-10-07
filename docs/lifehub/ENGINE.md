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


## Persistent engine daemon

The fourth engine slice turns the engine into a long-lived local platform process.

Start it with:

```sh
lifehub engine-serve
```

The daemon owns the live runner handles. Separate CLI invocations connect over the
authenticated local control plane instead of constructing their own engine:

```sh
lifehub engine-ping
lifehub engine-components
lifehub engine-executions
lifehub engine-start <component-ref>
lifehub engine-stop <execution-id>
```

The default transport is a local named pipe on Windows and a Unix-domain socket on
Unix-like systems. A random 256-bit auth key is stored locally and reused by client
commands.

This daemon is not a Web server and exposes no HTTP routes. It is an engine control
process. Restart policy, automatic activation and OS service installation remain
future engine work.


## First-class component model

Executable software is now declared independently from extension/shell surfaces.

A package can contain no UI contribution at all:

```toml
[[components]]
id = "worker"
runner = "lifehub.wasm"
contract = "lifehub.core-wasm@1"
provides = ["example.output@1"]
requires = ["example.input@1"]

[components.config]
module = "worker.wasm"
```

The Engine treats this as an executable component even when `contributes = []`.
The fields `provides` and `requires` are open interface identifiers; they are
not a closed list of app/domain types.

Legacy v0.1 executable contributions remain readable as a compatibility path,
but explicit `[[components]]` declarations are the primary execution model.

Core-Wasm execution was also decoupled from extension rendering: the bounded
Wasm runtime can now execute a first-class component directly from its package
identity, contract and component configuration.

This establishes the boundary needed for the next platform slice: Engine-level
interface resolution and capability routing.


## Capability-routed component interfaces

A component requirement is now enforceable platform state rather than descriptive
metadata.

For example:

```toml
[[components]]
id = "consumer"
runner = "example.runner"
requires = ["example.echo@1"]

[[components]]
id = "provider"
runner = "example.runner"
provides = ["example.echo@1"]
```

The Engine will not start the consumer until an authorized provider route exists.

Routing follows an explicit review/grant flow:

```text
consumer requires interface
        |
        v
review consumer + provider package snapshots
        |
        v
exact approval digest
        |
        v
grant snapshot-bound route
        |
        v
Engine resolves provider
```

Routes are bound to the exact approved digests of both packages. Package changes,
tampering or revocation fail closed. A consumer cannot request an undeclared
interface and a provider cannot be routed for an interface it did not declare.

The daemon control plane exposes route review, grant, resolve and revoke. The
operator CLI mirrors those operations with `engine-route-*` commands.

This slice only resolves authority and provider identity. Typed component-to-
component message transport is the next layer; interface routing must not be
implemented as arbitrary HTTP or direct process access.
