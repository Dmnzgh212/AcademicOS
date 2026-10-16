# C0 第二小步 · 运行命令受理与事件查询

日期：2026-10-15（Toronto）。代码起点：`ba33a4bcd691c293968b249fda19f927e9ba24e8`；前一步：[保存工作要求](C0-work-drafts.md)。

状态：**本地整理请求的去重受理、固定快照和持久事件查询已在隔离宿主中验证；未连接页面、实际浏览器存储或执行器。** 本步不执行任何运行步骤，不生成报告，不连接课程网站/浏览器/模型，不改 Engine/Core，不部署 Site。C0 的完整产品接入与真实执行验收仍未完成。

## 交付文件与复用

- [domain/run-commands.js](../domain/run-commands.js)：纯数据受理、命令记录查询、范围内运行摘要与事件分页。
- [adapters/run-command-controller.js](../adapters/run-command-controller.js)：复用上一阶段的同步宿主保存/回滚方式，保存确认后才返回受理结果。
- [tests/run-commands.test.mjs](../tests/run-commands.test.mjs)：8 项新增边界检查，包含实际临时 JSON 文件的保存与重开。

沿用已有 Site `dist/workflow.js` 中 `newRun` 的 request/docs/manualTexts/resources/steps/events 结构（核对修订 `4823905de9f34a56f06ee56dde70299c8b59460b`），在原 `state.runs` 中保存记录；新增 `state.runCommands` 只保存有界去重索引，不建立第二套运行数据库或通用 RPC。工作与材料范围复用 [C0 草稿模块](../domain/work-drafts.js) 和 [visibleDoc](../ui/document-scope.js)。

## 本步只受理什么

当前只支持 `organize`，工作已经保存为 revision ≥ 1，具有明确本地材料版本，且没有关联网站来源。learn、collect、plan、浏览器认证/导航/输入和任何外部操作均不在本步受理范围。材料/资源快照只用于固定这次请求，不表示已读取原件、应用 Skill 或执行脚本。

```js
const runs = createRunCommandController({
  getState: () => state,
  commit: mutation => change(mutation, '', false)
});
const receipt = runs.accept({
  contextId: projectId,
  commandId: commandIdSavedByCaller,
  workId,
  expectedRevision: workRevision,
  inputVersionIds: [documentVersionId],
  resourceRefs: [{resourceId: 'method', version: '1'}]
});
const page = runs.get({contextId: projectId, runId: receipt.runId, afterSeq: 0, limit: 50});
```

这是后续宿主接入示意，本次没有修改 app.js。resourceRefs 必须明确传入当前项目所选资源的确切版本与顺序；未选资源时传空数组。调用方在同一逻辑请求重试时保留原 commandId 和原请求内容，不用重新读取的新版选择替换重试内容。

### 受理和重试

1. 当前上下文允许访问，才查询以 `(contextId, commandId)` 为键的命令记录。
2. 同一个键、相同 workId/revision/材料版本顺序/资源版本顺序，返回原 runId/acceptedAt；不新增运行、事件或保存写入。后续修改工作和资源选择不重写历史请求。
3. 同一个键换了请求内容，返回 COMMAND_CONFLICT；另一个逻辑请求必须使用新的 commandId。
4. 新请求核对工作 revision、材料显式引用和项目资源选择；不跟随 latest，不自动跨项目补授权。
5. 将新运行、accepted 事件和命令去重记录放入同一次宿主保存。保存失败不返回成功；后续重试可重新受理。域函数返回的是待保存状态，不能绕过控制器把它当持久成功。

宿主仍须保证同步、单次 mutation、单写入方串行提交、真实保存确认和失败回滚。这里不是跨进程/多标签页的原子事务，不代替本地服务端授权。命令重试幂等也不等于外部操作的 exactly-once；本步没有任何外部执行动作。

### 固定的运行输入

新运行包含 workRevision、确切 inputVersionIds、白名单工作要求、材料元数据、受理时已保存的正文和所选资源版本/body 快照。未知的 token/cookie/authorization 等字段不会因整个对象复制而进入运行。输入与资源当前内容后续变化不会修改已保存快照。

尚无保存正文的原件不会被本步读取；字节 hash 没有重新核验。执行器接入时仍须确认原件身份、大小、读取范围与当前授权，不可把快照存在当作原件可读或执行获批。**不能直接交给未适配的旧 app.execute**：其部分恢复路径会用当前 documentTexts 重写 manualTexts，须先修正为遵守固定快照的执行适配。

### 运行与事件状态

受理后的 run.status 为 queued，cursor 为 0，四个步骤均 pending，materials/artifactIds 为空。只写一条真实的 accepted 事件：

`seq: 1 / kind: accepted / message: 运行请求已保存，等待本地执行器。`

它证明请求已保留，不证明步骤开始、材料已读、分析完成或成果已保存。没有自动把 queued 恢复成 running 的机制。

`runs.get` 返回 `lifehub.workstation.run@1`：运行标识、工作版本、步骤状态、输入/资源版本引用、inputScopeAvailable 和有序事件页。它不返回 manualTexts、资源 body 或完整内部 request/docs。材料引用撤销后历史摘要仍可查，inputScopeAvailable 为 false；不据此继续执行或释放正文。这个标志只检查当前引用范围，不检查原件是否存在。

事件以 afterSeq 增量读取，返回 lastSeq（当前末尾）和 nextSeq（本页最后一项，空页保留请求游标）。负数、越过末尾或非法分页大小拒绝；无新事件返回空页，不制造进度。事件顺序/标识异常拒绝，不自动修补历史。旧格式运行不静默改写，返回 UNSUPPORTED_RUN，继续从原记录查看。

## 本阶段上限

最多 1,000 条命令记录和 1,000 次运行；新受理到上限时拒绝，不自动丢弃旧去重记录。未来归档必须同时保留去重/恢复语义，不能简单 slice 掉历史。

每次最多 100 个材料版本、20 个资源；保存正文快照合计最多 120,000 字符单元，单资源 body 最多 12,000，资源 body 合计最多 120,000。超限整体拒绝，不截断。事件查询每页最多 100 条；本版事件记录校验上限 1,000 条。这些是隔离应用适配的边界，不是 Engine 总资源保障或产品最终容量承诺。

## 验证与恢复点

新增 8 项与前两步合计 **24 项 Node 检查通过**：

```sh
node --test tests/material-reader.test.mjs tests/work-drafts.test.mjs tests/run-commands.test.mjs
```

本步覆盖：受理后重开仍 queued/pending；事件游标不伪造进展；重试去重；同键换内容冲突；跨项目隔离；快照与未知字段边界；保存失败及恢复后重试；旧工作/缺输入/非本地模式拒绝；引用撤销；容量与快照上限。

测试使用合成材料、Node 临时文件和有回滚的同步宿主；确实重新读取保存的 JSON。没有验证实际浏览器存储、Windows 安装包、后台持续执行、真实课程来源或页面视觉。没有为此启动替代预览服务器。

下一小步可接一个固定的本地资料整理执行适配：先验证读取固定输入，再生成并保存确定性索引，逐步提交真实事件和产物。不要把所选资源 body 当任意代码解释，不接浏览器/模型；浏览器动作仍受监控和接管前置约束。W0 视觉核对仍待预览基础设施恢复，页面入口后接。保持 PR #74 Draft，不合并 main、不部署网站；GitHub 资料库继续只作候选。
