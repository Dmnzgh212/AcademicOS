# LifeHub platform status — 2026-10-06

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
| [#23](https://github.com/Dmnzgh212/AcademicOS/pull/23) | Platform entrypoint and handoff documentation | #22 |
| [#24](https://github.com/Dmnzgh212/AcademicOS/pull/24) | Scoped records contract and independent data shell | #23 |
| [#25](https://github.com/Dmnzgh212/AcademicOS/pull/25) | Shell lifecycle separation and configuration isolation | #24 |
| [#26](https://github.com/Dmnzgh212/AcademicOS/pull/26) | Fresh-environment installed-wheel validation | #25 |
| [#27](https://github.com/Dmnzgh212/AcademicOS/pull/27) | Reproducible developer examples companion | #26 |
| [#28](https://github.com/Dmnzgh212/AcademicOS/pull/28) | Exact reviewed grants and snapshot-bound capability handles | #27 |
| [#29](https://github.com/Dmnzgh212/AcademicOS/pull/29) | Egress redirect enforcement | #28 |
| [#30](https://github.com/Dmnzgh212/AcademicOS/pull/30) | Execution snapshot retention and review checkpoint | #29 |

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

The latest local full source run passed 221 tests. The count includes existing
AcademicOS tests and is not a completion percentage. CI runs 320 (#28) and 321
(#29) passed both supported Python versions, wheel installation and examples
archive smoke checks. #30 runtime-fix revision is recorded in the
[review checkpoint](PLATFORM_REVIEW_2026-10-06.md); consult live checks for the
latest documentation/test revision.

See [the prototype acceptance checklist](PROTOTYPE_ACCEPTANCE.md) and
[installed-wheel validation](WHEEL_VALIDATION.md).
Use the three example READMEs linked above for the real install → discover →
grant → execute → revoke paths. Digests must come from the reviewed package or
service output; examples do not auto-approve or silently grant capabilities.

## Remaining integration work

1. Keep final-revision source, installed-wheel and examples archive CI passing.
2. Independently review the cumulative stack against the #7 recovery anchor;
   the focused review checkpoint records findings and fixes, not full acceptance.
3. Make main integration and release publication separate explicit decisions.
   The examples companion build exists; no release has been published.

WIT/Component Model should be evaluated only when a concrete interoperability
need appears. PersonIR, a language and a compiler remain research until evidence
supports a distinct benefit over the conventional host/runtime path. No real
payment executor, calendar expansion or new approval product is part of this work.
