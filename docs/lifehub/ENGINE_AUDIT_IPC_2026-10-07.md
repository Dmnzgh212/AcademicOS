# Cumulative Engine audit: PRs #44–46

Reviewed at `65a467733557bd2802085f4df8242729e33a2271` after CI 349 passed
Python 3.11/3.12, 280 tests and existing wheel/platform/examples gates.

## Decision

Keep the Engine stack Draft. The bounded synchronous IPC slice is supported by
evidence; the complete Engine roadmap milestone is not yet accepted.

This follow-up changes only validation/documentation, not runtime/security code.

## Boundary checks

| Requirement | Finding |
|---|---|
| No Shell dependency | First-class Wasm consumer/provider need no contributes or presentation extension; installed-wheel smoke checks no Web/HTTP imports. |
| Caller identity | Guest supplies interface and JSON only. CoreWasmRunner constructs the callback using a host-selected component. Private callback constructors remain trusted host APIs. |
| Provider selection | Resolves only declared requirements against exact reviewed route grants. Guest payload provider/caller fields confer no authority. |
| Revocation | Checked before dispatch and before output release; mid-call revoke test rejects output. |
| Snapshot replacement | Both endpoints pinned; reinstallation/regrant of a changed approved snapshot cannot refresh the old callback. New execution is required. |
| Uninstall | Incoming interface grants removed; identical reinstall does not restore authority. |
| Resource limits | Reuses bounded JSON, memory/module/fuel limits; four combined legacy-service/interface calls per consumer invocation. Compilation wall time remains outside fuel bounds. |
| Operator control | Bad completed messages and authentication failures do not terminate the listener loop. Blocking incomplete handshake/frame remains a documented availability gap. |

## New installation evidence

`scripts/lifehub_component_ipc_smoke.py` runs with an installed wheel and `-I`,
asserts runtime imports are outside the checkout, and uses disposable local state.
It builds two ZIP-format `.lhpkg` files with first-class components, reviews and
installs them, verifies deny/grant/call/revoke, closes and recreates Engine,
checks terminal execution history and revoked authority, then verifies provider
uninstall and identical reinstall do not restore the route. No browser participates.

Local installed-wheel smoke passed on Linux/Python 3.12. CI runs it for both Python
versions. This is not Windows AF_PIPE or Windows service installation certification.

## Remaining architecture gaps

- Pure providers are invoked directly by the bounded service runner. They are not
  long-lived supervised provider instances with independent execution history,
  readiness, activation, restart policy or graceful shutdown.
- Current IPC is synchronous JSON compatibility, not typed WIT adoption, asynchronous
  events, cancellation, streams or a cross-process component transport.
- The control listener remains a trusted local operator endpoint. Malicious stalled
  clients need deadlines and resource policy before broader exposure.
- Recovery marks prior running rows interrupted; it is not evidence of a
  single-manager lease or survival of runner handles across process death.
- Arbitrary Python runners registered by the operator are trusted; these tests do
  not turn them into sandboxed guests.

## Next slice

Define and test explicit provider lifecycle/readiness semantics before claiming
background runtime completeness. Keep a separate WIT comparison experiment on the
adoption ledger. Do not begin compiler or Desktop UI implementation from this result.
