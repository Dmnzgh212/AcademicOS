# LifeHub v0.1 post-merge integration record

> **2026-10-09 审计标注（保留历史验收）：** 本文件所述 v0.1 **受限开发原型**的已接受结论不撤销；这不是用户产品、安全认证或今天的完整任务清单。旧“下一验收关卡/三款真实插件/外部独立验证”等历史安排已由 [LH-D-LOCAL-002](LOCALIZATION_AND_USER_ACCEPTANCE_DIRECTIVE.md)、[修订的 M1 标准](M1_ACCEPTANCE.md) 和 [全历史倒查](RETROSPECTIVE_AUDIT_2026-10-09.md) 更新解释。现阶段应先评估**真实需求与工程比例**；没有要求为小函数硬搬开源项目或把每项功能做成双 Wasm 包。具体优先级见 [文档索引](DOCUMENT_PRECEDENCE_AND_ARCHIVE_STATUS.md)。\n\n
LifeHub Platform v0.1 bounded developer prototype is **accepted**.
PR #32 merged into main at `690c0b9f0624617adcd3ed7e95341f8b9bb85f44`. Post-merge run 328 succeeded.
The historical filename is retained so existing links keep working.

## Exact recovery and scope

- Main base: `856b48a7adbb480d567d63c2582aa02d7405ce92`.
- Platform recovery: PR #7, `dc65605c0e84dcf545a8f8fdd7be176eb9c2a982`.
- Direction audit recovery: PR #16, retained separately.
- Validated implementation: PR #31, `bde9c72b70f5494a05a266b6396768fcf95932d1`.
- Original platform slices #1, #3–7 and resumed slices #17–31 remain available.
  PR #32 integrated their platform ancestry in one operation; no additional
  stacked-PR merges are needed for this baseline.
- Research PRs #2 and #8–16 are not integration sources. Historical research
  documents remain under `docs/lifehub/research`; no `experiments/person_ir`
  implementation or research test dependency is present.

## Automated cumulative review

| Area inspected | Result and retained evidence |
| --- | --- |
| Package parsing/install/removal | Reviewed-content approval, path/file/size checks, inert installation, verified execution bytes, outgoing/incoming grant removal and staged-request invalidation |
| Capability lifecycle | Explicit scoped reads, exact service binding, approval digest matches persisted binding, old handles reject changed approved content |
| Wasm host boundary | Explicit host imports, export signatures, approved module, memory/fuel/IO/count limits, shared finite/depth/byte JSON checks |
| Result and request release | Service output withheld after grant/package changes; staged Wasm output keeps starting digest, with final database check and submission in one transaction |
| Host decisions | Proposal base-record conflict checks, package/namespace binding, explicit effect approval, at-most-one attempt and uncertain-outcome handling; synthetic executor only |
| Presentation and transport | Detached catalog/records, stdlib independent shells, escaped reference output, scoped reads, loopback Host/Origin/token checks, disabled automatic egress redirects |
| Integration scope | Main is an ancestor, diff check clean, existing AcademicOS tests retained; modified application source stays under LifeHub |

Focused findings and regression proofs are recorded in
[the review checkpoint](PLATFORM_REVIEW_2026-10-06.md). This review was performed
by the implementing assistant, not an independent human or security auditor.
No remaining blocker was identified within the declared prototype trust model;
that statement is bounded by the limitations below.

## Validation gate

The implementation and merged tree match. Post-merge run 328 passed Python
3.11/3.12, Ruff, 228 pytest tests, wheel build/install, installed-wheel smoke,
platform lifecycle/HTTP smoke and reproducible extracted-examples smoke.
The accepted baseline has no identified blocker within its bounded trust model.

To repeat source checks from a clean candidate checkout:

```sh
python -m pip install -e '.[dev,wasm]'
python -m ruff check src tests examples/lifehub scripts/lifehub_wheel_smoke.py scripts/build_lifehub_examples.py
python -m pytest -q
```

Follow [wheel validation](WHEEL_VALIDATION.md) and
[examples distribution](EXAMPLES_DISTRIBUTION.md) for installed execution.
[Platform smoke](SMOKE_VALIDATION.md) also exercises the reader, independent
Shells, lifecycle rejection and real loopback HTTP requests.
Build wheel and examples from the same candidate commit. The builders and CI
exercise only temporary synthetic fixtures; no personal capabilities are granted.

## Merge and release boundary

PR #32 is merged. Preserve historical research branches and freeze Core.
After this docs cleanup passes CI, establish `v0.1.0-alpha.1` as the first Alpha
baseline. Tag creation is separate from GitHub Release publication.
Next validate at least three unrelated real plugins without Core modifications,
record evidence/friction, then audit whether changes belong to SDK/DX, ecosystem,
v0.2 Core or a justified restart of PersonIR research.

Retained limits: trusted local operator APIs; no remote/multi-user identity
boundary; filesystem and SQLite updates not globally atomic; no DNS pinning or
complete SSRF sandbox; Wasm compilation wall time not fuel-bounded; row-bounded
record exports without total-byte/pagination guarantees; reference workspace
storage in LifeStore; no real external effects, Mesh, WIT Component Model, or
accepted PersonIR compiler. Linux/Python CI is not cross-platform certification.
