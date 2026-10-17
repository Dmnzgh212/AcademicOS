# D0 · 固定版本材料的只读适配

日期：2026-10-15。代码起点：`24ca955f302eef021fd0951705ab407fd6097151`；[完整计划](IMPLEMENTATION_PLAN.md)。

状态：**独立适配器实现与 Node 边界验证完成；未接宿主/页面，未做真实 IndexedDB 或浏览器验收。** 本次不修改骨架、线上 Site、Engine、数据库或个人数据。GitHub 课程资料库继续仅为候选。

## 本步交付

- [material-reader.js](../adapters/material-reader.js)：`createMaterialReader({getState, readOriginal})`，只暴露 `getMaterial` 和 `readArtifact`。
- [material-view.schema.json](../adapters/material-view.schema.json)：`getMaterial` 的版本化 JSON 投影契约。它不是 Engine ABI，也不是持久数据库 schema。
- [material-reader.test.mjs](../tests/material-reader.test.mjs)：隔离验证固定版本、引用范围、实际原件状态、容量、异步期间失效和错误处理。

复用已有 [visibleDoc](../ui/document-scope.js) 的材料归属/项目引用规则，以及现有宿主的原件读取函数；不另建文件库、爬虫或通用权限系统。

## 宿主接入约定

后续宿主组合时可采用以下调用方式；本次没有把它写入线上 app.js：

```js
const reader = createMaterialReader({
  getState: () => state,
  readOriginal: id => fileOp('get', id)
});
const view = await reader.getMaterial({contextId: projectId, versionId: documentId});
const text = await reader.readArtifact({contextId: projectId, artifactId: view.text.artifactId});
```

`contextId` 目前对应宿主的课程/项目记录 ID；宿主必须提供已经允许访问的状态与存储。这里的范围检查用于避免页面串材料，**不是远程或不可信客户端的授权边界**。未来本地服务端仍须独立校验真实授权，不能信任客户端传入的 contextId、scope 或 libraryRefs。

`getState` 需包含 `projects`、`docs`、可选 `libraryRefs` 和 `documentTexts`。`readOriginal(id)` 仅返回该 ID 的 `Blob/File` 或空值；不接收路径、URL、任意脚本或写入操作。模块不请求网络、不写存储、不读取目录。

### 固定版本和投影

`versionId` 使用现有 `doc.id`，`materialId` 使用现有材料家族标识；旧记录缺少家族/序号时分别使用自身 ID/1。显式读取 v1 即使存在 v2 也返回 v1，不调用 latest 过滤。项目可通过材料家族引用读取历史版本，输入固定版本仍由后续 Run 契约绑定。

元数据返回材料名称、所有者上下文、前一版本/来源引用、原件与正文状态。返回对象不共享宿主记录，调用者修改它不会改原材料。contentHash 仅来自已有的合法 SHA-256 格式元数据；`integrity: not_checked` 明确表示本步未重新校验字节 hash，不能把它显示成“完整性已验证”。

产物 ID 是 `original:<versionId>` 或 `text:<versionId>`；只按记录 ID 解析，禁止路径形标识。未知版本和不可见版本统一返回 UNAVAILABLE。已保存的文件名、路径或 ready 标签不证明原件存在，必须查询实际存储。

| 状态 | 含义 |
| --- | --- |
| original.available | 宿主确实返回原件，且在本阶段大小限制内 |
| original.missing / too_large | 没有原件 / 超出本阶段读取范围；不删除已有记录 |
| text.available | 有已保存且长度允许的正文，空字符串也有效；不等于原件提取质量已核验 |
| text.pending_read | 存在可尝试读取的文本型原件，尚未验证编码和字符数；不能显示为“已提取” |
| text.not_extracted | 原件存在但 PDF 等格式尚无正文；显示等待解析，不假装已读懂 |
| text.missing / too_large | 无可用原件/正文，或超出读取限制 |

`readArtifact` 返回 `{artifactId, versionId, kind, mimeType, content}`；原件 content 是不可变 Blob，正文 content 是字符串。Blob 不属于 JSON 协议；未来 HTTP/IPC 接入须单独设计有鉴权的字节传输，不把此返回对象直接 JSON.stringify 当文件。

### 限制与失效

本阶段原件读取上限 2 MiB，正文上限 120,000 个 JavaScript 字符单元；超过就整体拒绝，不静默截断。它们是隔离适配实验的边界，不代表整个 LifeHub 的最终文件大小上限。只直接解码 UTF-8 文本型材料；PDF 原件可返回，但 PDF 正文、OCR、Office 解析仍属于 D3/后续能力。

原件读取和文本解码的异步返回前重新检查材料归属、版本记录和保存的正文。期间移除引用时不释放结果；同一版本被修改时返回 STALE_VERSION，避免新旧信息混合。它不取消已经开始的宿主 IO，也不等于 Engine 权限撤销实现；宿主返回字节的身份正确性和生命周期仍由宿主负责。

错误码包含 INVALID_ID、UNAVAILABLE、INVALID_STATE、STALE_VERSION、MISSING_ORIGINAL、NOT_EXTRACTED、TOO_LARGE、UNSUPPORTED_ENCODING、READ_FAILED、INVALID_HOST_RESULT。宿主异常只给可理解的通用提示，不把内部路径/账号细节直接返回界面。调用方负责按文本安全渲染名称/正文；本模块不渲染 HTML，也不执行材料里的代码。

## 验证与接续

在本模块根目录运行：

```sh
node --test tests/material-reader.test.mjs
```

使用 Node 内置 test、Blob 和 TextDecoder，无新依赖。8 项检查覆盖：固定历史版本及不改宿主、越界读取在 IO 前拒绝、原件缺失与空正文、PDF 不冒充已提取、实际字节/字符超限、异步期间取消引用、版本变更、错误编码与宿主错误脱敏。测试材料均为合成数据；不是课程账号、真实浏览器或已安装 Windows 产物证据。schema 已做 JSON 语法检查，未声称使用完整 JSON Schema 验证器验证运行结果。

W0 仍受预览基础设施限制：本轮重试 `sites-preview start` 返回 `bwrap: Can't mount proc on /newroot/proc: Operation not permitted`，页面未启动，未获取截图。遵守 [Sites 排障说明](skill://plugin_connector_1p_689987207de08191979cf68eca2941c6/sites/references/troubleshooting.md)：“An unavailable supervisor, browser, or static-preview dependency is an environment limitation; do not replace managed infrastructure or change working application code to compensate.” 未改用独立服务器或其他浏览器路径。

接续：优先恢复 W0 实际页面核对；通过后 W1 才把读取器接到原材料槽位。D0 的本地 transport、服务端授权和旧数据迁移没有因此完成；可继续独立接入实验，但不能直接迁移个人数据。保持 Draft、不合并 main、不部署网站。
