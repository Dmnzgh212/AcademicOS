# LifeHub platform status — 2026-10-05

LifeHub is an open personal computing platform. The platform branch advances
Package, Capability, Wasm Runtime, internal contracts and replaceable Shell.
Calendar planning is the existing AcademicOS application. Proposal and fake-effect
review are host mechanisms and reference interfaces, not the definition of LifeHub.

## Reviewable branch structure

The [recovery record](PLATFORM_RECOVERY_2026-10-05.md) identifies the original
main, platform and PR #16 audit anchors. The resumed platform stack is:

| PR | Slice | Base PR |
| --- | --- | --- |
| [#17](https://github.com/Dmnzgh212/AcademicOS/pull/17) | Catalog contracts and generic reader | #7 |
| [#18](https://github.com/Dmnzgh212/AcademicOS/pull/18) | Exact service authorization and review digests | #17 |
| [#19](https://github.com/Dmnzgh212/AcademicOS/pull/19) | Bounded JSON computation service | #18 |
| [#20](https://github.com/Dmnzgh212/AcademicOS/pull/20) | Package-bound guest service bridge and revalidation | #19 |
| [#21](https://github.com/Dmnzgh212/AcademicOS/pull/21) | Independent catalog shell and consistent discovery | #20 |
| [#22](https://github.com/Dmnzgh212/AcademicOS/pull/22) | Shared JSON message validation before provider dispatch | #21 |

These are draft review units, not merged releases. Do not merge the whole
research stack into main or treat the existence of a PR as acceptance.
The platform branch contains no `experiments/person_ir` implementation or test
dependency. Original research branches retain that work and its evidence.

## Implemented paths and boundaries

| Area | Current behavior | Contract / example |
| --- | --- | --- |
| Package | Review archive contents, approve a digest, install and revalidate managed bytes; uninstall removes relevant grants | [Package installation](PACKAGE_INSTALLATION.md) |
| Discovery | Detached `lifehub.catalog@1` JSON; package and extension metadata from one discovery result; arbitrary extension points preserved | [Extension contracts](EXTENSION_CONTRACTS.md) |
| Capability | Manifest requests do not grant authority; storage scopes and exact service bindings are enforced by the host | [Reader example](../../examples/lifehub/reader/README.md), [service authorization](SERVICE_ACTIVATION.md) |
| Core Wasm | Explicit approved entrypoint, bounded memory/fuel, mediated host imports, no WASI | [Wasm runtime](WASM_RUNTIME.md) |
| JSON service | Fresh bounded computation instance; no storage/effects/network imports; response released only after success and final grant/package revalidation | [JSON ABI](JSON_SERVICE_ABI.md) |
| Guest bridge | Caller identity comes from the installed package, never a guest-supplied caller ID; at most four calls per run | [Guest calls](GUEST_SERVICE_CALLS.md), [echo example](../../examples/lifehub/json_echo/README.md) |
| Shell | CLI/web reference consumers and a standalone text/static-HTML catalog consumer | [Independent shell](../../examples/lifehub/catalog_shell/README.md) |

JSON service messages reject nonfinite numbers, exceedance of 64 KiB raw or
canonical bytes, and container nesting beyond 64 levels. Invalid guest requests
are rejected before provider callbacks. Catalog discovery is metadata only;
it grants no authority and is not an atomic filesystem snapshot or execution token.

The CLI is a trusted local administrative interface. It is not a multi-user or
remote authorization boundary. Package revalidation tests cover controlled changes,
not a proof against all concurrent filesystem races. Fuel bounds guest execution,
not module compilation wall time. The independent shell demonstrates discovery
presentation, not complete parity with the reference workspace.

## Reproduce the current validation

From this platform branch, using Python 3.11 or 3.12:

```sh
python -m pip install -e '.[dev,wasm]'
python -m ruff check src tests examples/lifehub
python -m pytest -q
```

The latest local full run through #22 passed 184 tests. This count includes existing
AcademicOS tests; it is not a percentage of platform completion. GitHub CI runs
Python 3.11 and 3.12. At the status check for this document, the newest #21 and #22
runs were queued; prior #21 input-validation commit passed. Consult live PR checks
before accepting any slice.

Use the three example READMEs linked above for the real install → discover →
grant → execute → revoke paths. Digests must come from the reviewed package or
service output; examples do not auto-approve or silently grant capabilities.

## Next engineering work

1. Define a minimal data-access contract for a second shell, with explicit host
   authorization and detached results. Prove it against two independent consumers
   before extending the reference workspace UI.
2. Reduce direct shell dependence on kernel/storage internals around that proven
   interface. Keep package identity and permission decisions in the host.
3. Review the stacked platform diffs and their CI before proposing integration.
   Main integration remains a separate decision; this document authorizes no merge.

WIT/Component Model should be evaluated only when a concrete interoperability
need appears. PersonIR, a language and a compiler remain research until evidence
supports a distinct benefit over the conventional host/runtime path. No real
payment executor, calendar expansion or new approval product is part of this work.
