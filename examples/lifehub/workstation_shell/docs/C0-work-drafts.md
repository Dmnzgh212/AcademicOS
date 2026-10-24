# C0 第一小步 · 保存工作要求

日期：2026-10-15。代码起点：`ca8dfe1ee1057fa04d4c5b9a6269a09849c22759`；[完整计划](IMPLEMENTATION_PLAN.md)。

状态：**草稿数据逻辑、宿主保存控制器和隔离验证完成。尚未接页面或实际浏览器存储；未实现运行受理和事件持久化，不能标记整个 C0 完成。** 不改 PPT 布局、线上 Site、Engine/Core 或个人数据。GitHub 课程资料库存储仍为候选。

## 本次交付

- [domain/work-drafts.js](../domain/work-drafts.js)：在现有 `state.requests` 上准备创建/更新草稿，生成读取投影；不自行写存储。
- [adapters/work-draft-controller.js](../adapters/work-draft-controller.js)：复用宿主同步保存/回滚入口，确认宿主保存成功后才返回成功结果。
- [tests/work-drafts.test.mjs](../tests/work-drafts.test.mjs)：8 项新增检查，包含临时 JSON 文件保存重开，以及与 [D0 读取器](D0-material-reader.md) 的固定版本连接。

没有创建另一份 Work 数据库。字段和四种工作方式沿用已有 Site `dist/workflow.js` 的 `newRequest`（核对修订 `4823905de9f34a56f06ee56dde70299c8b59460b`）：`title/goal/deliverable/mode/docIds/sourceIds` 与既有 requests 保持兼容。小范围本地适配新增了 revision、显式草稿状态、引用校验、长度超限报错；原有静默截断不沿用。材料范围继续复用 [visibleDoc](../ui/document-scope.js)。

## 保存与读取契约

```js
const controller = createWorkDraftController({
  getState: () => state,
  commit: mutation => change(mutation, '', false)
});

const work = controller.save({
  contextId: projectId,
  draft: {
    title: 'Lecture review',
    goal: '根据选定课堂材料整理要点。',
    deliverable: '带来源引用的笔记',
    mode: 'learn',
    docIds: [documentVersionId],
    sourceIds: []
  }
});

const reopened = controller.get({contextId: projectId, workId: work.workId});
// 更新同一工作时，必须同时传 workId 与读取到的 expectedRevision。
```

上面是后续宿主接入示意，本次没有修改 app.js 或新增创建表单。commit 必须同步、只调用 mutation 一次，在同一宿主串行更新范围内保存，并在失败时恢复上次状态；成功返回 true，失败返回 false/抛错。控制器不提供自己的通用事务系统，也不假定异步保存已完成。未来本地服务需独立保证实际事务、权限和持久化；浏览器内检查不等于服务端授权。

### 工作记录

原记录仍使用 `id/projectId/goal/deliverable/docIds/sourceIds`。新增保存从 revision 1 起；旧记录没有 revision 时读取为 0，第一次修改必须显式使用 expectedRevision 0，再保存为 1。修改时保留原 id、created 和其他历史元数据，更新 updated，进入 draft 状态。

读取投影 `lifehub.workstation.work-draft@1` 返回 `workId/contextId/title/instruction/expectedOutput/mode/revision/status/materialRefs/sourceIds`，并标注 completeness 与 missing。新保存的 status 为 draft，保存动作不会启动运行；旧记录读取时保留既有状态。`specified` 只表示引用和要求已填写，不证明原件存在、正文已提取或具备执行权限。

| 行为 | 本次处理 |
| --- | --- |
| 缺少学习/整理材料 | 可保存要求，missing 标 materials，待补充 |
| 采集方式尚无来源 | 可保存要求，missing 标 source；不会自动打开浏览器 |
| 选中旧版本 | 保留确切 doc.id；有新版也不自动替换 |
| 跨项目材料引用 | 只接受已有显式材料引用；来源仍须属于当前项目 |
| 引用保存后被移除 | 重开显示 unavailable，不读取或显示越界材料的家族/版本元数据；修正选择后再保存 |
| 并发编辑旧 revision | 拒绝覆盖并返回 REVISION_CONFLICT；必须重新读取 |
| 已保存的运行 | 修改草稿不修改 state.runs 或其 request/input 快照 |
| 保存失败 | 不返回成功；存储回滚由宿主承担；错误提示不透出内部路径 |

创建时无需 expectedRevision，或显式使用 0；更新时必须与当前 revision 相等。此机制依赖宿主的单写入方与串行提交，不是 localStorage 多标签页之间的原子 compare-and-swap。新建草稿重复提交也不做 commandId 去重；执行命令幂等性属于 C0 下一步。

限制沿用既有工作字段：名称最多 100 字符、要求 12,000 字符、期望产物 2,000 字符，每类引用最多 100 项。显式超限拒绝，不悄悄丢失要求。名称可从要求首行派生，完整要求仍保存。空处理要求和未知执行方式拒绝；输入对象中的运行状态、脚本命令等额外字段不会变成可执行动作。

纯数据函数 `saveWorkDraft` 返回新的 state 与工作投影，不原地修改传入状态。控制器才在宿主 mutation 内赋值 requests；未改动的其他状态按普通不可变更新共享引用。工作投影和新草稿数组与输入草稿脱离，界面修改投影不会修改已保存记录。

## 验证

本轮运行新增工作测试与上一阶段材料读取测试，共 **16 项通过**：

```sh
node --test tests/material-reader.test.mjs tests/work-drafts.test.mjs
```

新增 8 项覆盖：缺材料的要求可保存并从文件重开；revision 冲突；固定历史版本及越界材料/来源；保存失败；引用被撤销后重开与修正；旧记录 revision 0 和运行快照保留；跨项目工作与 ID 冲突；超长/畸形要求不截断、不写入。

测试使用 Node 临时文件和原子替换模拟一个有回滚的宿主，重开时确实重新读取 JSON。跨模块检查从重开的工作引用进入 D0，取回旧版本正文而非最新版。所有材料均为合成数据。它们不证明浏览器 localStorage/IndexedDB、Windows 已安装产物或生产宿主的事务能力；不宣称已修复原宿主保存后渲染报错等其他问题。

## 中断接续

本轮不重复尝试尚无恢复证据的预览基础设施。W0 实际截图核对仍待完成，W1 不能据此标记通过。

下一项可独立完成 C0 的第二小步：受理本地确定性步骤的运行命令，保存命令 ID、固定工作 revision/输入/资源快照及真实事件，再验证重复命令不重复启动和重开恢复。不要直接接浏览器、定期采集、模型、监控或全部页面。页面线在 W0 通过后再接读取器和创建入口。

保持 PR #74 Draft，不合并 main，不部署网站。
