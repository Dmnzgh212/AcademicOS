# LifeHub platform status — 2026-10-06

> **2026-10-09 审计标注（保留历史验收）：** 本文件所述 v0.1 **受限开发原型**的已接受结论不撤销；这不是用户产品、安全认证或今天的完整任务清单。旧“下一验收关卡/三款真实插件/外部独立验证”等历史安排已由 [LH-D-LOCAL-002](LOCALIZATION_AND_USER_ACCEPTANCE_DIRECTIVE.md)、[修订的 M1 标准](M1_ACCEPTANCE.md) 和 [全历史倒查](RETROSPECTIVE_AUDIT_2026-10-09.md) 更新解释。现阶段应先评估**真实需求与工程比例**；没有要求为小函数硬搬开源项目或把每项功能做成双 Wasm 包。具体优先级见 [文档索引](DOCUMENT_PRECEDENCE_AND_ARCHIVE_STATUS.md)。

LifeHub is an open personal computing platform. The accepted main baseline provides
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
| [#31](https://github.com/Dmnzgh212/AcademicOS/pull/31) | Consistent JSON bounds across Wasm host imports | #30 |

These historical slices were integrated by PR #32. LifeHub v0.1 prototype
acceptance is **accepted**; this is an Alpha developer baseline, not ecosystem
completion. Research branches remain separate.
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

Accepted merge baseline: `690c0b9f0624617adcd3ed7e95341f8b9bb85f44` (PR #32).
Post-merge GitHub Actions [run 328](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37412182124)
succeeded on Python 3.11 and 3.12: Ruff, 228 pytest tests, wheel build/install,
installed-wheel smoke, platform lifecycle/HTTP smoke and examples archive smoke.
The test count includes AcademicOS tests and is not a completion percentage.

See [the prototype acceptance checklist](PROTOTYPE_ACCEPTANCE.md) and
[installed-wheel validation](WHEEL_VALIDATION.md).
Use the three example READMEs linked above for the real install → discover →
grant → execute → revoke paths. Digests must come from the reviewed package or
service output; examples do not auto-approve or silently grant capabilities.

## Real-plugin validation phase

Core is frozen. Validate at least three unrelated plugins (academic information,
RSS/news, and local system information) using the existing Package, Capability,
Runtime, Service and Shell contracts. Keep domain logic out of Core and record
friction before proposing v0.2. Alpha tagging follows the docs cleanup CI.

A Core change requires evidence: two unrelated plugins need one mechanism,
a reproducible security/lifecycle issue, an existing demand the contract cannot
express, or a demonstrated Shell abstraction failure. Speculation is insufficient.

PersonIR remains research-frozen. Restart only after repeated real-plugin evidence
shows a material problem that ordinary API design, host checks and capability
policy cannot naturally resolve. Known Alpha limits above remain accepted unless
real use demonstrates a blocker. No release has been published.
