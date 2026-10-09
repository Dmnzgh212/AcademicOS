# LifeHub PR #1–#72 全量历史声称与处置台账

**审计时间 2026-10-09；结论层级：PR 元数据与原报告全量追踪，关键代表代码/CI 深入抽查；不是 72 个 PR 的逐行安全代码审计。** 详细方法、限制与处置见 [倒查总报告](RETROSPECTIVE_AUDIT_2026-10-09.md)。

截至本次快照：#1、#32、#33 已合并 main；其余 69 个 PR 尚未合并。#3–#31 若显示 Draft，是它们的历史独立 PR 未合并；相应开发成果经累计 #32 纳入 main，**不能错误地再逐一合并**。其余 #34–#72 是不同阶段的研究/文档/运行草案，CI 成功不自动成为已发布功能。

表中“有效”仅指相应陈述有对应设计/测试证据，不等于实用性、安全性、主干合并或全局接受。“未完成”不意味着测试失败。标签与局限在具体 PR 原文/CI 中详细说明。

| PR | 对象 | 倒查判定/可保留的准确表述 |
|---|---|---|
| [#1](https://github.com/Dmnzgh212/AcademicOS/pull/1) | 研究交接 | 已合并；只是文件/研究交接，不是运行系统验收 |
| [#2](https://github.com/Dmnzgh212/AcademicOS/pull/2) | 独立 PersonIR 实验 | 研究 No-Go 结论有意义；不支持编译器落地 |
| [#3](https://github.com/Dmnzgh212/AcademicOS/pull/3) | 包审查安装 | 原型机制；经 #32 集成，不能视为生产包生态 |
| [#4](https://github.com/Dmnzgh212/AcademicOS/pull/4) | 有限 Wasm 运行 | 受限 host API 机制；经 #32 集成，非通用沙箱认证 |
| [#5](https://github.com/Dmnzgh212/AcademicOS/pull/5) | 提案/提交 | 常规安全宿主机制有效；不能作为 PersonIR 原创性证据 |
| [#6](https://github.com/Dmnzgh212/AcademicOS/pull/6) | 外部效果账本 | 测试用 fake effect；不等于真实邮件/支付交付 |
| [#7](https://github.com/Dmnzgh212/AcademicOS/pull/7) | 本地审批页面 | 参考 Shell；不能让 LifeHub 定义为审批仪表盘 |
| [#8](https://github.com/Dmnzgh212/AcademicOS/pull/8) | PersonIR 基础语义 | 研究切片；不属于产品完成 |
| [#9](https://github.com/Dmnzgh212/AcademicOS/pull/9) | PersonIR 授权 | 研究切片；宿主授权实验 |
| [#10](https://github.com/Dmnzgh212/AcademicOS/pull/10) | PersonIR 提交 | 研究切片；真实域系统价值未证 |
| [#11](https://github.com/Dmnzgh212/AcademicOS/pull/11) | PersonIR 假效果 | 研究切片，fake executor 不等于外部执行 |
| [#12](https://github.com/Dmnzgh212/AcademicOS/pull/12) | PersonIR 来源/流 | 封闭模型实验；不等于端到端安全证明 |
| [#13](https://github.com/Dmnzgh212/AcademicOS/pull/13) | 异质场景 | 合成场景覆盖；不等于实际业务可用 |
| [#14](https://github.com/Dmnzgh212/AcademicOS/pull/14) | 敌对案例 | 发现原生宿主边界问题；研究成果有效 |
| [#15](https://github.com/Dmnzgh212/AcademicOS/pull/15) | Wasm 对照 | 支持暂缓新编译器；否定证据有效 |
| [#16](https://github.com/Dmnzgh212/AcademicOS/pull/16) | 方向审查 | 指出早期研究/工程错序；不属于验收签发 |
| [#17](https://github.com/Dmnzgh212/AcademicOS/pull/17) | 平台契约恢复 | 经 #32 集成；旧 PR 保留草案历史 |
| [#18](https://github.com/Dmnzgh212/AcademicOS/pull/18) | 服务授权绑定 | 经 #32 集成；限本地宿主授权范围 |
| [#19](https://github.com/Dmnzgh212/AcademicOS/pull/19) | JSON 计算服务 | 经 #32 集成；不是任意复杂应用支持 |
| [#20](https://github.com/Dmnzgh212/AcademicOS/pull/20) | Wasm 客户端绑定 | 经 #32 集成；有限同步 ABI |
| [#21](https://github.com/Dmnzgh212/AcademicOS/pull/21) | 独立元数据 Shell | 经 #32 集成；不是完整桌面 Shell |
| [#22](https://github.com/Dmnzgh212/AcademicOS/pull/22) | JSON 有界校验 | 发现并修复输入不一致；有效安全修复 |
| [#23](https://github.com/Dmnzgh212/AcademicOS/pull/23) | 项目入口文档 | 解释改善；无新增可运行用户功能 |
| [#24](https://github.com/Dmnzgh212/AcademicOS/pull/24) | 受控 records 契约 | 经 #32 集成；分页/总字节等限制存在 |
| [#25](https://github.com/Dmnzgh212/AcademicOS/pull/25) | Shell 生命周期分离 | 经 #32 集成；展示层尚非完整迁移 |
| [#26](https://github.com/Dmnzgh212/AcademicOS/pull/26) | wheel 安装验证 | 经 #32 集成；对应环境有效 |
| [#27](https://github.com/Dmnzgh212/AcademicOS/pull/27) | 示例归档 | 经 #32 集成；开发者伴随包非用户安装器 |
| [#28](https://github.com/Dmnzgh212/AcademicOS/pull/28) | 授权与包快照 | 明确修复授权一致性；有效安全回归 |
| [#29](https://github.com/Dmnzgh212/AcademicOS/pull/29) | 网络跳转校验 | 明确修复允许列表绕过；有效安全回归 |
| [#30](https://github.com/Dmnzgh212/AcademicOS/pull/30) | 执行包身份保留 | 明确修复阶段性身份失配；有效安全回归 |
| [#31](https://github.com/Dmnzgh212/AcademicOS/pull/31) | 统一 JSON 边界 | 明确修复其他 host import 校验；有效安全回归 |
| [#32](https://github.com/Dmnzgh212/AcademicOS/pull/32) | v0.1 集成 | 已合并，有限开发原型功能接受；非产品完成 |
| [#33](https://github.com/Dmnzgh212/AcademicOS/pull/33) | v0.1 接受记录 | 已合并，记录 CI328 与有限范围；非独立审计 |
| [#34](https://github.com/Dmnzgh212/AcademicOS/pull/34) | 课程/RSS/系统三域 | CI 通过的模拟/半真实适配；不能称3款完整真实插件 |
| [#35](https://github.com/Dmnzgh212/AcademicOS/pull/35) | Engine 协调者 | 早期 Draft 切片，单独不代表真实后台能力 |
| [#36](https://github.com/Dmnzgh212/AcademicOS/pull/36) | 执行账本 | 早期持久化，不等于 guest 恢复完成 |
| [#37](https://github.com/Dmnzgh212/AcademicOS/pull/37) | 本地 Engine 控制 | 控制协议，不是远程/多用户权限边界 |
| [#38](https://github.com/Dmnzgh212/AcademicOS/pull/38) | 持久 Engine daemon | daemon 存活不等于后台 guest 真实工作 |
| [#39](https://github.com/Dmnzgh212/AcademicOS/pull/39) | Shell 分离 | 隔离展示依赖有价值；非消费者体验完成 |
| [#40](https://github.com/Dmnzgh212/AcademicOS/pull/40) | 工作区存储拆分 | Core 领域/界面解耦，迁移风险应保留 |
| [#41](https://github.com/Dmnzgh212/AcademicOS/pull/41) | 组件 manifest | 基础设施切片；不是可用插件生态 |
| [#42](https://github.com/Dmnzgh212/AcademicOS/pull/42) | 接口路由 | 元数据/授权不等于真实 live IPC |
| [#43](https://github.com/Dmnzgh212/AcademicOS/pull/43) | 平台开源先例 | 研究知识，不等于接入成熟组件 |
| [#44](https://github.com/Dmnzgh212/AcademicOS/pull/44) | 卸载路由修复 | 复现重装复权 Bug；必要安全修复 |
| [#45](https://github.com/Dmnzgh212/AcademicOS/pull/45) | 错误客户端隔离 | 控制服务韧性测试；仍受阻塞客户端限 |
| [#46](https://github.com/Dmnzgh212/AcademicOS/pull/46) | Wasm 组件 IPC | 真实但同步、有界且受控；非通用跨进程 RPC |
| [#47](https://github.com/Dmnzgh212/AcademicOS/pull/47) | IPC 累积检查 | 安装 wheel/IPC smoke；不是 M1 完成 |
| [#48](https://github.com/Dmnzgh212/AcademicOS/pull/48) | ready/关闭清理 | 生命周期修复；后续仍需进程回收证据 |
| [#49](https://github.com/Dmnzgh212/AcademicOS/pull/49) | 独占 Engine 管理者 | 复现并修复重复管理；有效稳定性保障 |
| [#50](https://github.com/Dmnzgh212/AcademicOS/pull/50) | Windows AF_PIPE | Windows CI 行为验证；非所有 Windows 版本认证 |
| [#51](https://github.com/Dmnzgh212/AcademicOS/pull/51) | WIT 研究 | 独立比较有效；无生产组件模型准入 |
| [#52](https://github.com/Dmnzgh212/AcademicOS/pull/52) | 一次性第三方应用 | 真实包/进程；不是持久后台 guest |
| [#53](https://github.com/Dmnzgh212/AcademicOS/pull/53) | 持久 Wasm guest | 后台状态切片有效；无自动重启 |
| [#54](https://github.com/Dmnzgh212/AcademicOS/pull/54) | 进程死亡监控 | 无 Shell 监控有效；无自动恢复 |
| [#55](https://github.com/Dmnzgh212/AcademicOS/pull/55) | 卸载即终止 | 运行期间安装身份检查；后续持续审查 |
| [#56](https://github.com/Dmnzgh212/AcademicOS/pull/56) | M1 验收门槛 | 外部人类作者要求过高，已按新范围修订 |
| [#57](https://github.com/Dmnzgh212/AcademicOS/pull/57) | 监控失败/清理 | 失效闭合与锁清理；限定环境行为 |
| [#58](https://github.com/Dmnzgh212/AcademicOS/pull/58) | 有界重启与意图 | 真正恢复关键功能；并不保证零重叠 |
| [#59](https://github.com/Dmnzgh212/AcademicOS/pull/59) | 证据留存 | 产物可追溯；日志自洽不等于真实性证明 |
| [#60](https://github.com/Dmnzgh212/AcademicOS/pull/60) | 第三方集成指南 | 工程侧适用；用户不能被要求学习 Wasm |
| [#61](https://github.com/Dmnzgh212/AcademicOS/pull/61) | stop-death 竞争修复 | 复现回归；M1 未自动验收 |
| [#62](https://github.com/Dmnzgh212/AcademicOS/pull/62) | 最高指导/复用指令 | 方向有价值；复制优先仍需价值与比例前置审查 |
| [#63](https://github.com/Dmnzgh212/AcademicOS/pull/63) | 权限先例研究 | 研究资料而非已集成业务能力 |
| [#64](https://github.com/Dmnzgh212/AcademicOS/pull/64) | 授权 trace/PROV 适配 | 仅有界研究证据；不能证明新语言优势 |
| [#65](https://github.com/Dmnzgh212/AcademicOS/pull/65) | AI 能源模块 | 真实 Engine 集成演示合格；非真实能源产品 |
| [#66](https://github.com/Dmnzgh212/AcademicOS/pull/66) | 用户操作目标 | UX 文档合格；不是已交付 Windows 入口 |
| [#67](https://github.com/Dmnzgh212/AcademicOS/pull/67) | M1 复审 | 准确暴露资源/证据范围；不是最终批准 |
| [#68](https://github.com/Dmnzgh212/AcademicOS/pull/68) | 故障 OS 退出观测 | 增强可重现证据；不证明零瞬时重叠 |
| [#69](https://github.com/Dmnzgh212/AcademicOS/pull/69) | M1 汇总候选 | 合并准备文档；不是 M1 accepted/main merge |
| [#70](https://github.com/Dmnzgh212/AcademicOS/pull/70) | 账本失败处理 | 复现新故障并修复，CI394；需纳入后续候选 |
| [#71](https://github.com/Dmnzgh212/AcademicOS/pull/71) | 自然排序本地化 | 18测和跨平台演示有效；选题/工程比例不合格 |
| [#72](https://github.com/Dmnzgh212/AcademicOS/pull/72) | Windows 排序试用包 | CI401 离线菜单验证；建立在低价值演示上，冻结扩张 |

## 横向验收裁定

**维持原判但限定范围：** #1 研究交接已合并；#32/#33 的“有限开发者平台原型”已接受。过去明确说明的信任与数据限制不变。#28–#31、#44、#49、#61、#70 的复现缺陷和修复证据不应因方向调整而被否定。

**验收声称降级：** #34 三域验证不是三款日常使用插件；#52 不是持久应用、#53/54 单独不是自动恢复；#65 是人工合成数据工程实验；#69 只是受限 Alpha 候选；#71/72 只是排序能力与试用包装实验，不算高价值本地化产品。

**研究保留但不转生产：** #2/#8–#16、#51、#63/#64 的结论用于判断是否值得新机制，不以“测试通过”解释为语言/编译器上线依据。

**工程新门槛：** 接下来重要的非 Core 应用模块，先通过使用价值与比例决策；小函数可直接实现，无强制源码复制或两包工程化。M1 的二包、安全与后台测试只属于 M1 验收。不找外部人类插件作者，也不降低真实安全审查。

## 未完成的进一步审查，不能用表格掩盖

- 本表核对全部 72 条历史 PR 声称，但**没有复核每条分支每个文件的完整代码路径、所有签名与调用图**；需要安全认证/正式公开发行时，另行针对候选合并树进行完整代码安全审查。
- 已获取部分关键 CI 日志、文档和源码；未重放所有历史 CI artifact 或人工复现所有历史 Windows 环境结果。过期或不可下载的证据一律不能凭描述补造。
- 现阶段无完整软件供应链签名、发行机制和终端用户实际设备验证；这些不能因 #72 提供 ZIP 就标为通过。

下一步不需要对研究与废弃分支逐一复跑全部旧实验；对**打算合并/发行的精确累积树**做集成差异、授权/资源/故障场景重点复测，既彻底覆盖新风险又不重复消耗已经撤回的旧方向。
