# Bounded component interface calls

This first data-plane slice reuses `lifehub.service-json@1`; it does not choose
the final universal ABI. WIT remains an isolated comparative experiment.

A first-class core-Wasm consumer imports `lifehub.call_interface_json` with the
same six-i32 memory signature as the legacy service call: interface pointer/length,
JSON request pointer/length, response pointer/capacity. It supplies an interface
identifier, never a caller or provider authority claim.

The trusted CoreWasmRunner creates an invocation-local closure from its resolved
ComponentDescriptor. Declared routes are captured as exact consumer/provider
package snapshots. Each call resolves current authority and compares that snapshot;
the provider is selected only through the approved route. Response release repeats
the authorization/snapshot check. Revocation or package changes fail closed.

Providers must be first-class `lifehub.wasm` components with the
`lifehub.service-json@1` contract, an approved module and no downstream requirements.
They execute through the existing pure JSON service runner with no storage, effects,
WASI or ambient imports. They do not need a UI contribution or legacy service grant.

Existing JSON finite/depth/64 KiB bounds, module/memory/fuel bounds apply.
Legacy service and interface calls share the existing four-call per consumer-run
budget. No new serialization or production dependency is introduced.

Authority fields inside request JSON are ordinary domain data. The closure and
runner setup are trusted host APIs, not guest-facing identity constructors.
This does not sandbox arbitrary Python runners registered by the local operator.

Current scope: synchronous request/response to pure Wasm providers. No streams,
async events, nested provider calls, cancellation, readiness/restart semantics or
WIT guarantee. Calls are fuel bounded; compilation wall time remains a known
Alpha limitation. This slice does not complete the Engine roadmap milestone.

Tests cover actual Wasm consumer/provider calls without Shell, deny-before-grant,
host identity despite forged payload fields, revoke including during response,
uninstall/tamper of either endpoint and retained JSON bounds.
