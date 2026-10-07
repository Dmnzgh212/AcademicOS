# Engine cumulative audit — 2026-10-07

Scope: Draft PRs #35–42, inspected at `35a243e75eaf5f5f361dbb36aa39160ae4355552`.
Read alongside ENGINE_ROADMAP_2026-10-07 and the reference study/adoption ledger
on the separate research branch. Those documents are not assumed to be merged.

## Decision

Keep the stack in Draft. Do not call the Engine milestone accepted yet.
This audit fixes one reproduced lifecycle security regression before component IPC.

## Findings

| Area | Evidence / remaining work |
|---|---|
| Shell separation | Engine imports kernel/registry/routing; control uses local JSON IPC rather than HTTP. Explicit components can exist without presentation contributions. |
| Presentation storage | Workspace persistence is separated from LifeStore in the stack. Preserve migration compatibility in the optional reference shell. |
| Interface routing | Exact consumer/provider content digests and explicit review/grant are implemented. Resolution is authority selection, not component message transport. |
| Uninstall authority | **Reproduced bug:** provider uninstall leaves incoming `component.interface` grants. Identical reinstall restores the old route without a fresh grant. This slice deletes incoming routes in the uninstall transaction, as existing service grants already do. |
| Runtime identity | Future guest IPC must obtain identity from a host execution context. A public operator `resolve(consumer_ref, interface)` API is not sufficient evidence of guest identity binding. |
| Supervision | Ledger recovery marks running work interrupted. Close currently closes storage; it does not prove graceful runner shutdown, readiness, crash restart/backoff, or a single-manager lease. Do not claim full supervisor semantics. |
| Control availability | `serve_forever` propagates accept/decode/response errors. Malformed or oversized messages and bad authentication need resilience tests before daemon acceptance. |
| Cross-platform | AF_UNIX tests explicitly skip Windows. AF_PIPE implementation selection is not Windows acceptance evidence. |
| WIT adoption | Still an isolated comparative spike. Retain the bounded JSON/core-Wasm compatibility path; add no production dependency for the experiment. |

## Reproduction and verification

The new regression test grants a route, uninstalls either endpoint, installs the
identical archive, and requires resolution to remain denied. Before the fix:
provider case failed (authority revived), consumer case passed. After the fix:
both cases pass in the full suite.

Local Python 3.12: 257 passed, two existing AF_UNIX transport tests blocked by
the execution environment (`socket.socket` raises EPERM). Ruff passed. The full
suite was attempted without altering or skipping those tests. Remote CI must
validate both transport tests, wheel installation and existing smoke gates.
Local results do not certify Windows or daemon availability under hostile clients.

## Next coherent slices

1. Control-plane malformed-input/authentication resilience, with bounded behavior.
2. Execution-scoped interface invocation and next-call revocation checks, with
   actual consumer/provider calls, snapshot replacement and uninstall tests.
3. Provider readiness/on-demand activation and explicit shutdown/recovery policy.
4. Same interface in an isolated WIT/Component Model comparison.

Do not combine these into a broad rewrite. PersonIR semantics research remains
separate; no compiler implementation is included in this audit.
