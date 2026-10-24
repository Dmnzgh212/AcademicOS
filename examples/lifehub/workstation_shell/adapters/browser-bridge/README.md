# LifeHub 本地浏览器连接

这是工作站 v0.3.1 的本地连接组件，针对 Windows 桌面 Chrome / Edge。需要在用户电脑安装一次；当前开发环境没有完成你的 Windows 实机验证。

## 安装与开始

1. 解压 `LifeHub-browser-bridge.zip`。
2. 在 Chrome 打开 `chrome://extensions`，或在 Edge 打开 `edge://extensions`。
3. 开启开发者模式，选择「加载已解压的扩展程序」，选择包含 `manifest.json` 的目录。
4. 打开需要读取的来源网页并登录。在该标签页点击 LifeHub 扩展，选择「绑定当前页面」。只向这个来源申请访问权限。
5. 打开工作站 → 来源 → 添加来源。地址与绑定页面一致；默认读取 `main, [role="main"]`。若范围不存在或匹配多处，调整为一个明确区域，例如 `body`。选 body 会包括该页导航，仍不等于读取整门课程。
6. 点来源的「绑定页面」，选择刚绑定的页面；然后「检查」。变化项进入 lib，HTML 原件与正文分别保留。
7. 在 lib 中选择「整理到本地目录」，选择 Windows 文件夹，生成 `lib/courses` 或 `lib/projects`、原件、正文、来源记录与 `index.json`。原文件与正文分开保存，旧版本保留。

## 轮询与监控

- 来源的「轮询」可选择5/15/30/60分钟。保持浏览器运行、绑定标签页打开。后台刷新前检查输入内容；发现草稿、登录或页面地址改变就记录错误。轮询可能受浏览器休眠影响，不保证精确钟点。
- 扩展缓存一份待归档快照；工作站打开后每15秒接收。未归档的变化不会被后续变化覆盖。首次归档后，后续无变化不建新版本、不重复解析或写入索引。
- 在绑定页面的扩展弹窗启用监控，再到工作站运行监控选择页面，开始预览。监控使用绑定 tabId 的 CDP 截图，每2秒请求一次；不使用活动标签截图，也不录制桌面。
- Chrome 会显示调试提示，这是 `debugger` 权限用于页面监控的提示。打开该页面 DevTools 或取消调试可能断开监控；工作站显示冻结原因，并暂停自动读取。
- 工作站浏览器页的「打开浏览器」仅聚焦已绑定并核对地址的原标签页，不改变自动控制权。若已经加载旧版扩展，更新解压目录后在扩展管理页点击重新加载，并刷新工作站网页。
- 暂停禁止后续动作，等待当前动作结束才确认；接管还会打开原页面。交回前重新核对地址与输入状态。停止保留已经归档内容，不撤销已经发送的请求。
- 同一绑定页只有一个工作站标签页持有控制权；需要切换工作站时，在扩展重新绑定。浏览器重启后需重新绑定，避免复用过时 tabId。

## 现有 ChatGPT 对话

1. 打开已经建立的 ChatGPT 会话（网址中有 `/c/`），用扩展绑定该页。启用监控可同时观看该页。
2. 工作站保存一项「阅读与学习」需求并开始。正文读取完后，在执行页点击「发送到绑定聊天」。
3. 选择目标会话，发送一次并等待读回。已有草稿或正在生成会阻止发送；不备份后覆盖草稿。
4. 取得独有结束标记、页面不再生成并稳定后，完整回复进入同一工作，保存聊天回复与学习记录。
5. 超时、会话变化或结果不确定时不会重发。查看原会话后可停止等待并手动导入回复。

## 当前边界

本版真实接入路径是单个已加载网页范围，不会遍历 Brightspace 的所有课程、分页、PDF 或嵌入文件。PDF / Office 正文自动提取、PowerShell 后台进程和外部日历尚未接通。AcademicOS 的 Brightspace 数据集采集与 manifest 保留为专门适配路线，没有复制成另一个通用内核。Skill 可显式选择版本，会话习惯蒸馏继续暂停。

网页 DOM 和 Chrome API 测试使用 Node 模拟，不能代替真实 Windows、Brightspace 和 ChatGPT 网页验收。监控帧仅在界面内存中显示，不保存到工作区备份。采集与聊天数据留在本浏览器，不要求模型 API。

实现依据：
- https://developer.chrome.com/docs/extensions/reference/api/debugger
- https://developer.chrome.com/docs/extensions/reference/api/scripting
- https://developer.chrome.com/docs/extensions/reference/api/alarms
- https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-captureScreenshot
