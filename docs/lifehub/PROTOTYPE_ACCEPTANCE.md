# LifeHub v0.1 prototype acceptance

> **2026-10-09 审计标注（保留历史验收）：** 本文件所述 v0.1 **受限开发原型**的已接受结论不撤销；这不是用户产品、安全认证或今天的完整任务清单。旧“下一验收关卡/三款真实插件/外部独立验证”等历史安排已由 [LH-D-LOCAL-002](LOCALIZATION_AND_USER_ACCEPTANCE_DIRECTIVE.md)、[修订的 M1 标准](M1_ACCEPTANCE.md) 和 [全历史倒查](RETROSPECTIVE_AUDIT_2026-10-09.md) 更新解释。现阶段应先评估**真实需求与工程比例**；没有要求为小函数硬搬开源项目或把每项功能做成双 Wasm 包。具体优先级见 [文档索引](DOCUMENT_PRECEDENCE_AND_ARCHIVE_STATUS.md)。

LifeHub Platform v0.1 bounded developer prototype acceptance: **accepted**.
PR #32 merged at `690c0b9f0624617adcd3ed7e95341f8b9bb85f44`. Post-merge CI run 328 succeeded.
Acceptance applies to the declared prototype trust model, not a complete ecosystem,
security certification, real effects or PersonIR. Core is frozen for real use.

| Gate | Evidence | Assessment |
| --- | --- | --- |
| Platform/research separation | Main omits experiments/person_ir and research test dependencies | Accepted; research frozen |
| Package and Capability lifecycle | Install/digest/grant/revoke/tamper/uninstall and execution snapshot tests | Accepted within local trust model |
| Runtime/service path | Core-Wasm, bounded JSON ABI, package-bound guest calls | Accepted |
| Replaceable Shell | Detached catalog/records and independent consumers; HTTP smoke | Accepted; reference persistence limit retained |
| Source matrix | Run 328, Python 3.11/3.12, Ruff, 228 pytest tests | Passed |
| Installed wheel | Run 328 build/install and installed-wheel smoke | Passed |
| Platform lifecycle/HTTP smoke | Run 328 | Passed |
| Examples archive | Run 328 repeat-build/extracted examples smoke | Passed |
| Main integration | PR #32 merged; main baseline above | Accepted |
| Alpha tag/publication | v0.1.0-alpha.1 follows docs cleanup CI; no Release published | Next action |

## Review order

Review #17 then #18–20 for package/contract/authorization/runtime behavior;
#21–22 for discovery presentation and message boundaries; #23–25 for documentation,
records mediation and shell lifecycle; #26–27 for installed distribution and examples; #28–31 for authorization,
transport and execution snapshot fixes.
Each draft targets its preceding branch. Approval of an isolated slice is not
approval of the whole stack. Retain the research stack separately.

The cumulative platform review and fixes were integrated through PR #32.
Historical review slices and research branches remain available. See
[the review checkpoint](PLATFORM_REVIEW_2026-10-06.md) and
[the post-merge integration record](INTEGRATION_CANDIDATE.md).

## Limits retained in this prototype

The CLI and Python shell APIs are trusted local interfaces. They are not remote
identity or multi-user boundaries. Data exports require authorized host choices;
there is no general information-flow proof. Controlled package-change tests do
not prove all filesystem race cases. Fuel does not bound compilation wall time.
Record reads have a row bound, not pagination or a total byte bound. Reference
workspace persistence remains in LifeStore, although startup is separated.
Examples are not bundled into the wheel. No real external effect executor,
Personal Mesh, WIT integration, source language or compiler is accepted here.

Do not use test counts or PR counts as a completion percentage. Report the gates
above as verified, pending or outstanding, with the exact evidence available.

## Next acceptance gate

[INTEGRATION_CANDIDATE.md](INTEGRATION_CANDIDATE.md) records the merged baseline and retained limits.
The next gate is three unrelated real plugins running without Core changes,
with controlled permissions/data lifecycles and an ecosystem friction record. The assistant's review does not substitute for independent human review.
