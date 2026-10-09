# LifeHub 文档效力和历史审查索引（2026-10-09）

此页是**历史文档阅读索引**，避免将旧研究愿景、受限测试样例或未合并 Draft 误作当前产品任务。**本页也是 Draft，不代表 main 已接受。**

## 一、如何读不同年代的材料

| 类型 | 文件 / 来源 | 现在应如何使用 |
|---|---|---|
| 当前项目方方向 | [LH-D-LOCAL-002](LOCALIZATION_AND_USER_ACCEPTANCE_DIRECTIVE.md) | 优先审查业务价值；合适的复杂开源代码合法移植、裁剪、本地化；工程侧安全，用户侧简单 |
| 方向补充纠偏 | [防过度执行决策标准](ANTI_OVEREXECUTION_DECISION_GATES.md) | **审计建议**：小函数简单做；M1 测试两个模块不是产品插件通用要求；验收技术与价值分离 |
| 平台基本原则 | [CORE_VISION_AND_HIGHEST_DIRECTION.md](CORE_VISION_AND_HIGHEST_DIRECTION.md) | 个人主权、撤销授权、Engine/Shell 分离、Core 领域无知；阅读时优先看最新增补 |
| 旧复用决议 | [ENGINEERING_REUSE_DIRECTIVE.md](ENGINEERING_REUSE_DIRECTIVE.md) | LH-D-REUSE-001 的“直接接入优先”已被 LH-D-LOCAL-002 修订；复杂基础依赖可按风险继续采用 |
| M1 当前工程关卡 | [M1_ACCEPTANCE.md](M1_ACCEPTANCE.md) | 后台 guest/权限/故障的真实 Engine 工程验证；不用外部人类插件作者；不是每项产品都需两包 |
| 最新审计与候选 | [M1_TECHNICAL_REVIEW_2026-10-08.md](M1_TECHNICAL_REVIEW_2026-10-08.md)、[M1_INTEGRATION_CANDIDATE_2026-10-08.md](M1_INTEGRATION_CANDIDATE_2026-10-08.md) | 通过项必须携带限定范围；#70 恢复账本修复应进入候选；M1 尚未签发 |
| 过去已合并基线 | [PROTOTYPE_ACCEPTANCE.md](PROTOTYPE_ACCEPTANCE.md)、[INTEGRATION_CANDIDATE.md](INTEGRATION_CANDIDATE.md)、[PLATFORM_STATUS.md](PLATFORM_STATUS.md) | v0.1 **有限开发原型**正式接受的历史事实；其中旧“下一门槛/外部审查”等不自动作为现行命令 |
| 历史研究与交接 | [OPEN_PLATFORM_RESEARCH.md](OPEN_PLATFORM_RESEARCH.md)、[HANDOFF_2026-09-28.md](HANDOFF_2026-09-28.md)、[DIRECTION_AUDIT_2026-10-03.md](DIRECTION_AUDIT_2026-10-03.md) | 概念方案、研究路径、当时的疑难与 No-Go，不是立即开发全部 UI/语言/插件市场的任务清单 |
| 技术样例 | #34、#65、#71/#72 | #34 合成数据和受控数据通路，#65 后台合成能源工程样例，#71/#72 排序与 Windows 菜单试用；不能替代高价值业务模块 |
| 全历史纠偏 | [RETROSPECTIVE_AUDIT_2026-10-09.md](RETROSPECTIVE_AUDIT_2026-10-09.md)、[PR #1–#72 声称台账](RETROSPECTIVE_CLAIM_LEDGER_2026-10-09.md) | 明确什么已测、什么仅演示、什么工程投入失衡、什么尚未验证 |

**历史事实不可改写**：旧 CI 何时通过、代码何时合并、受限原型何时接受，仍按当时提交记录。**新命令不得从旧“下一步建议”自动推出**：发生范围冲突时按项目方后来明确的本地化目标，先检查价值、比例和安全边界，必要时单独请求澄清。

## 二、已知歧义词语及其唯一操作解释

- **独立 / 第三方**：独立于 LifeHub Core 的安装、运行和授权，不必来自外部人类编程者。
- **开放**：可组合、可扩展、可替换；不是自动允许任意外部代码/云服务直接读个人数据。
- **复制优先**：有价值、足够复杂的业务开源能力才选择性复制/适配；**不强迫复制普通排序等小函数**，也不建议 fork 底层加密、数据库或 Wasm VM。
- **合格/成功/PASS**：先辨明“测试场景通过”“安全边界局部证明”“实际用户价值”“产品可交付”“合并批准”，不可互换。
- **真实插件**：源码和测试包可以是真实可运行，输入仍可能是模拟/人工文件；不得悄悄升级为“已自动连接用户真实服务”。
- **Windows 优先**：真实用户的安装体验优先 Windows；Linux 的基础 Engine CI 有价值，不意味着每项应用功能都要开发 Linux UI。
- **Core 不修改**：普通业务功能不写死进 Core；已经复现的通用权限/故障 Bug 可依法修复，不意味着完全冻结必要安全修补。
- **用户安全验证**：用户可以拒绝过宽权限和复制脱敏错误；审查第三方依赖、执行沙箱、构建供应链和压力测试是工程责任。
- **M1**：限定后台监督的技术里程碑；其通过不意味着 LifeHub 产品完成或所有 Alpha 风险消失。

> **分支同步提示（2026-10-09）：** 本索引存在于 Draft #73 分支中；所列「当前」指项目方最新表达的方向，而非每份文件均已在 `main` 生效。#62 的本地化决议与 #56 的 M1 标准随后增补了反过度执行条款，但 #73 自身所带对应文件并非相同 blob 版本。不得只因相对链接可打开就认定跨分支最新修订已整合；提交合并方案前应逐文件比较并记录最终版本。完整差异及界限见 [全历史审计 F7](RETROSPECTIVE_AUDIT_2026-10-09.md)。

## 三、审计层级必须如实披露

覆盖全部 PR 1–72 的**状态和声称**核验已经完成；代码/日志做了有代表性的重点深入审查。没有把 72 个 PR 的每个源文件逐行安全审计，也没有用用户个人 Windows 环境验证分发包。最终安全整合仍必须针对**拟合并的准确累计树**进行改动审查、重点风险和 Windows 真实运行验证，不能凭这份索引自动 merge。
