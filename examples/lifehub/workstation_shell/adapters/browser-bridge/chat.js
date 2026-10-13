(() => {
  if (globalThis.__lifehubDemoInstalled) return;
  globalThis.__lifehubDemoInstalled = true;
  let current = null;
  const visible = e => e && !!e.getClientRects().length;
  const text = e => (e.innerText ?? e.textContent ?? "").trim();
  const clean = value => value.replace(/[\u200B\uFEFF]/g, "").replace(/\u00A0/g," ").trim();
  const draftOf = e => "value" in e ? e.value : (e.innerText ?? e.textContent ?? "");
  const sleep = ms => new Promise(resolve => setTimeout(resolve,ms));
  const send = message => chrome.runtime.sendMessage(message).catch(()=>{});
  function one(selector) {
    const elements = [...document.querySelectorAll(selector)].filter(visible);
    if (elements.length !== 1) throw new Error("页面结构不匹配：" + selector + "；未自动发送。");
    return elements[0];
  }
  function busy() {
    return [...document.querySelectorAll("button")].some(b => visible(b) &&
      (/^(Stop generating|Stop streaming|停止生成|停止流式传输)$/i.test(b.getAttribute("aria-label") || "") ||
      b.getAttribute("data-testid") === "stop-button"));
  }
  function answers(marker, tag) {
    // 兼容常见桌面会话标记；未匹配时保守超时，不把整页内容当回复。
    const explicit = [...document.querySelectorAll('[data-message-author-role="assistant"]')];
    const candidates = explicit.length ? explicit : [...document.querySelectorAll('article,[role="listitem"]')];
    return candidates.filter(visible).map(e => {
      const body = e.querySelector(".markdown");
      return {whole:text(e),body:text(body || e)};
    }).filter(e => !e.whole.includes(tag) && e.body.includes(marker));
  }
  async function run(task) {
    const id = task.id;
    const marker = "LH_DONE_" + id;
    const tag = "[LifeHub任务 " + id + "]";
    const prompt = tag + "\n" + task.question + (task.material ? "\n\n材料：\n" + task.material : "") +
      "\n\n为便于本地脚本保存，请在回答最后单独一行原样输出：" + marker + "\n请不要在其他位置重复这行标记。";
    const progress = status => send({type:"progress",id,status,url:location.href});
    const alive = () => { if (current?.id !== id) throw new Error("已停止等待。"); };
    const startPath = location.pathname;
    let sent = false;
    try {
      if (location.hostname !== "chatgpt.com") throw new Error("目标不是 ChatGPT。");
      if (busy()) throw new Error("聊天正在生成。等当前回复结束再运行。");
      const editor = one('#prompt-textarea,[contenteditable="true"][role="textbox"],textarea[placeholder],#mobile-composer-prompt');
      const draft = draftOf(editor);
      if (clean(draft)) {
        if (!task.backupDraft) throw new Error("检测到聊天草稿：" + clean(draft).slice(0,60) +
          "\n可先清空聊天输入框，或勾选‘先备份文字草稿’后运行。草稿尚未改动。");
        const saved = await chrome.runtime.sendMessage({type:"draft",id,draft});
        if (!saved?.ok) throw new Error("草稿备份失败，未覆盖、未发送。");
      }
      editor.focus();
      if (editor.tagName === "TEXTAREA") {
        Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set.call(editor,prompt);
        editor.dispatchEvent(new Event("input",{bubbles:true}));
      } else {
        const selection = window.getSelection();
        const range = document.createRange(); range.selectNodeContents(editor);
        selection.removeAllRanges(); selection.addRange(range);
        if (!document.execCommand("insertText",false,prompt))
          throw new Error("当前编辑器不接受脚本输入。未发送，请检查网页。");
      }
      if (clean(draftOf(editor)) !== clean(prompt))
        throw new Error("输入内容核对失败。未发送，请检查草稿。");
      let button;
      for (let attempt=0; attempt<30; attempt++) {
        alive();
        button = one('button[data-composer-submit],button[data-testid="send-button"],button[aria-label="Send prompt"],button[aria-label="Send message"],button[aria-label="发送消息"]');
        if (!button.disabled && button.getAttribute("aria-disabled") !== "true") break;
        await sleep(100);
      }
      if (button.disabled || button.getAttribute("aria-disabled") === "true")
        throw new Error("发送按钮不可用。未发送，请检查登录状态或草稿。");
      alive();
      button.click(); sent = true;  // 整个运行只点击一次；后续失败不会重新发送。
      await progress("已点击发送，正在等待本次完整回复…");
      const deadline = Date.now() + 180000;
      let last = "", stableSince = 0;
      while (Date.now() < deadline) {
        await sleep(500); alive();
        if (startPath !== "/" && location.pathname !== startPath)
          throw new Error("会话已切换，停止读取。已发出的提问不会重发。");
        const found = answers(marker,tag);
        if (found.length > 1) throw new Error("出现多个匹配回复，停止自动保存。");
        const answer = found[0]?.body || "";
        if (answer !== last) { last = answer; stableSince = Date.now(); }
        const lines = answer.split("\n").map(line=>line.trim()).filter(Boolean);
        // 独有的尾部标记 + 非生成状态 + 稳定窗口，避免仅靠固定等待时间。
        if (lines.at(-1) === marker && !busy() && Date.now()-stableSince >= 2000) {
          const clean = answer.slice(0,answer.lastIndexOf(marker)).trim();
          if (!clean) throw new Error("回复只有标记，没有正文。");
          await send({type:"done",id,answer:clean,url:location.href});
          return;
        }
      }
      throw new Error("等待超过 3 分钟，或页面回复结构/结束标记未匹配。提问不会重发，请在网页查看结果。");
    } catch(error) {
      if (current?.id === id) await send({type:"error",id,error:error.message +
        (sent ? "\n已经点击发送，请检查聊天后再决定是否另发。" : "")});
    } finally { if (current?.id === id) current = null; }
  }
  chrome.runtime.onMessage.addListener((message,_sender,reply) => {
    if (message.type === "restore") {
      try {
        if (current || busy()) throw new Error("仍在运行或生成，请先等结束。");
        const editor = one('#prompt-textarea,[contenteditable="true"][role="textbox"],textarea[placeholder],#mobile-composer-prompt');
        if (clean(draftOf(editor))) throw new Error("输入框已有内容，未恢复，以免覆盖。");
        editor.focus();
        if (editor.tagName === "TEXTAREA") {
          Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set.call(editor,message.draft);
          editor.dispatchEvent(new Event("input",{bubbles:true}));
        } else if (!document.execCommand("insertText",false,message.draft)) throw new Error("恢复失败。");
        if (clean(draftOf(editor)) !== clean(message.draft)) throw new Error("恢复内容核对失败，请检查网页。");
        reply({ok:true});
      } catch(error) { reply({ok:false,error:error.message}); }
      return;
    }
    if (message.type === "cancel") { if (current?.id === message.id) current = null; reply({ok:true}); }
    if (message.type === "run") {
      if (current) return reply({ok:false,error:"这个标签页已有任务。"});
      current = message.run;
      reply({ok:true});
      void run(message.run);
    }
  });
})();

