# 实现前研究：已有能力、真实缺口与复用决定

核对日期：2026-10-15。本文记录源码检查与官方资料，不是运行证明；本次无生产代码变更、无依赖安装、无真实账号采集或 Windows 验收。执行顺序见 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)。

## 1. 核对范围

| 来源 | 固定修订 | 用途 |
| --- | --- | --- |
| AcademicOS main | `da298481802aeb67386531153b521568b8c50ef5` | 来源采集、数据库、文件 manifest、日程与本地宿主 |
| 工作站 UI / PR #74 | `0f85947391ea344b5c66331d2ddaf048ab75f63b` | 现有组件、扩展、宿主 patch、01/02 阶段记录 |
| 已有 Site 源码 | `4823905de9f34a56f06ee56dde70299c8b59460b` | 实际页面执行、浏览器存储、lib 导出、桥接与报告能力 |
| 方向文件 / PR #62 | `e9d0150059710f49de9aa37362af5bd20cc4555e` | Core 方向、LH-D-LOCAL-002 及其价值/比例纠偏；文件仍在 Draft |
| M1 集成候选 / PR #69 | `33a076e0b9578a6427c2c075369e43953a50b069` | 已有后台能力的候选复用来源；文档明确 M1 NOT ACCEPTED |

不把不同分支拼成一个已经存在的发布版本。不自动合并以上 Draft；后续适配选择具体版本时重新核对其最新状态。

## 2. 可以接着用什么

下表 main 路径均在上述固定修订下核对；UI 路径相对 `examples/lifehub/workstation_shell/`；Site 路径相对其 `dist/`。

| 能力 | 代码/资料证据 | 复用决定与缺口 |
| --- | --- | --- |
| 指定课程采集 | main `src/academicos/sources/brightspace/collector.py`、`client.py`；`docs/SOURCE_COLLECTION.md` | 已有按端点隔离的采集与规范化；优先适配结果，不重建课程爬虫框架。源码存在不代表用户学校每个端点均可用 |
| 会话复用 | main `src/academicos/sources/brightspace/auth.py` | 已实现持久浏览器 profile 与本地 token 复用路径；`docs/BRIGHTSPACE_INGESTION.md` 中“以后实现”的描述已落后于源码。真实登录/过期恢复仍需验证；凭证与 profile 不传到 Shell 或提交 Git |
| 无变化少下载 | main `src/academicos/sources/manifest.py`、`brightspace/downloads.py` | 复用远端 fingerprint + 本地文件检查；当前快速判断含大小检查，不每次重算文件 hash，不能声称防所有本地篡改 |
| 游标和来源健康 | main `sources/state.py`、`health.py`、`sync.py`、`store.py` | 复用每来源状态、成功游标与哈希；source_items upsert 不是完整不可变 lib 历史，后者仍需应用适配 |
| Windows 定时检查 | main `sources/windows_scheduler.py`、`scheduler_cli.py` | 已用系统 schtasks 调用同一 Python 同步；当前最小间隔 15 分钟。它不是 Windows service，不保证机器睡眠时实时执行，也不等同受管 Engine guest |
| 日程领域 | main `calendar/extract.py`、`truth.py`、`inbox.py`；`planner/engine.py` | 复用事实/候选/计划语义；接 UI 前验证时区、证据和变更行为，不直接让原始公告改事实日历 |
| 本地宿主模式 | main `lifehub/web.py` | 已有 loopback、Host/Origin、变更 token、安全响应头。当前接口不是通用文件读取/工作执行 API；不能直接给旧 handler 加任意路径和脚本参数 |
| 工作区与安排 | UI `ui/workbench.js`、`schedule.js`、`shell.js`、CSS | 复用展示函数、时间轴和状态模型；现有组合仍与 PPT 不符。按模式修结构，不因代码已存在就原样照搬 |
| lib 与来源 | UI `ui/library.js`、`sources.js`、`document-scope.js` | 版本选择、课程范围与原件检查可复用；宿主落地目录和 Python 数据库尚未连通 |
| 单目标浏览器桥 | UI `adapters/browser-bridge/worker.js` 等 | 复用明确 tab/URL/范围绑定、目标锁与控制确认；不是所有网页通用爬虫，也不默认抓取当前 active tab |
| 运行固定输入 | Site `workflow.js`、`station.js`、`app.js` | 已快照材料、来源与资源；需要应用层持久化与唯一写入方。现有执行在网页里，关闭网页不能宣称后台继续 |
| 版本化导出 | Site `lib-folder.js` | 原件/文本/source.json/index.json 和课程/项目目录已有；当前每次重写文本/索引，尚不符合完整无变化跳过 |
| 安全基础报告 | UI `ui/markdown.js`；Site 报告保存路径 | 可显示基础 Markdown。无复杂公式/表格/图片的完整支持；fixture 曲线由演示代码插入，不是分析执行产物 |
| 图标 | UI `vendor/lucide-source.json` 及 notices | 本地摘取与归属已有，保留许可证和来源；不再加在线图标加载器 |

## 3. 不应误判为已完成的部分

- 浏览器捕获在读取页面后对文本/链接做指纹比较；可避免新增相同材料，但不意味着已经跳过所有请求和读取。
- 原件 PDF 能显示不等于文本可供学习。现有网页自动读取主要限文本型文件，PDF/Office 尚需解析适配或人工文本；当前限制含 2 MB blob、120k 文本等，扩大前要逐项验证，不通过静默截断制造完整报告。
- 单来源待消费快照只有一个槽：不同新版到达时拒绝覆盖旧版，能保留待消费数据，但不能保证每个中间版本都被采到。以后需要有界队列/背压与漏采说明；首个闭环先验证显式冲突反馈。
- 浏览器绑定使用 session storage；浏览器重启后不能假定 tab 绑定仍有效。恢复需重新校验，不自动把旧 tabId 指向的新页当原来源。
- 实时帧临时保存，约 2 秒采样；暂停或失联应标为冻结/历史。帧只反映可见目标区域，不是每一瞬间完整录屏。
- 聊天桥按既有 `/c/` 会话绑定，遇草稿/繁忙拒绝自动输入；含按 run 去重和不确定结果不重发策略。DOM 模拟通过不代表真实登录页面稳定，仍需有范围的实际回归；不要清空草稿来“解决阻塞”。
- 现有 collect 保存材料和记录后，没有自动形成“工作读取并保存成果”的完整链。该连接是 I1 的实际交付，不是 UI 加按钮即完成。
- 资源目录目前可保存说明与版本，并不代表任意脚本都能执行。选一项有价值的受控脚本即可，不为每个小功能扩出编译器/两个 Wasm 包/专用分发体系。
- M1 候选有受限后台/进程故障恢复证据，但仍列出总资源上限、活锁监测、并发撤销等限制，且未获 M1 验收。不能拿其合成样例当用户资料工作流已跑通。

## 4. 外部成熟能力只在真实缺口处引入

| 需求 | 比较与当前决定 | 后续最小实验 |
| --- | --- | --- |
| PDF 阅读 | 现有原生 viewer 无新增依赖；PDF.js 可控制逐页渲染、缩放等。W1 先原生；需要精确控件/提取时考虑 PDF.js | 固定版本与 Apache-2.0 notice，离线 worker，实际 PDF/错误/大文件测试；不先复制整个通用 viewer 或自己写 parser |
| 报告渲染 | 基础安全 Markdown 已有；高级 Markdown/公式需成熟 parser/净化库。当前不新加依赖 | 以实际报告样本检查缺失项，再比较最多 1–3 个适合的维护中实现，记录版本、许可证、安全配置与替换边界 |
| 全文检索 | 首个闭环用材料清单/文本定位足够；无需向量数据库 | 确有跨资料查询后，核对已有搜索与 SQLite FTS5 可用性；索引由文本派生键驱动 |
| 后台/调度 | 现有 schtasks 与 M1 候选各有范围；扩展 alarm 只承担浏览器内定期事件 | 先手动单次检查，再验实际 Windows 周期、浏览器/机器重启、错过周期和重复启动；不自建通用 scheduler |

官方资料于本日查阅：

- [Chrome service worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)：worker 可能被终止，内存全局变量会丢失，需要持久化与恢复设计；不能用一个常驻假设证明可靠后台。
- [Chrome alarms](https://developer.chrome.com/docs/extensions/reference/api/alarms)：设备睡眠时不唤醒机器，错过重复周期不会逐次补跑。当前文档列出 Chrome 150+ `persistAcrossSessions`，早期 Chrome/其他浏览器仍需启动校验；不可对 Chrome/Edge 所有版本一概宣称重启持久。项目需实测目标版本后才采用新字段。
- [PDF.js examples](https://mozilla.github.io/pdf.js/examples/) 与 [API](https://mozilla.github.io/pdf.js/api/index.html)：有加载/页面/viewport/渲染能力；接入不等于已经解决扫描件 OCR、阅读顺序和公式提取。候选保持固定本地依赖，后续提交再记录实际采用版本，不虚构现在已选定的版本。

## 5. 研究结论如何约束下一步

保留已认可的设计，先 W0 校对骨架，再 W1 接阅读器。数据线使用已有来源与文件代码，先做 D0 隔离只读适配；I1 证明一个有用闭环后，再分模块接 lib、监控、资源和安排。后台持续运行单列 B0/B1，不把浏览器演示或 Engine 测试当成该承诺。每一步有自己的产物与检查点，不以“大量模块同时提交”证明进展。
