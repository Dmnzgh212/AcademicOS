import {icon} from '../../ui/icons.js';

// Slide-2 layout only. No state store, file reader, run controller or network calls.
const tool=(name,label)=>`<button class="s02-icon-button" type="button" disabled aria-label="${label}" title="骨架阶段：${label}尚未接入">${icon(name,17)}</button>`;
export function workspaceSkeleton(){
 return `<div class="s02-workspace" data-stage="02">
  <aside class="s02-sidebar" aria-label="项目导航">
   <div class="s02-brand">LifeHub</div>
   <details class="s02-project-tree" open>
    <summary>${icon('folder',20)}<span>Engineering / Fall</span>${icon('chevron-down',16)}</summary>
    <div class="s02-project selected" aria-current="page">${icon('folder',19)}<span>Signals Lab</span></div>
    <div class="s02-project">${icon('folder',19)}<span>Robotics</span></div>
    <div class="s02-project">${icon('folder',19)}<span>Algorithms</span></div>
   </details>
   <div class="s02-sidebar-bottom">${icon('link',18)}<span>Connections</span></div>
  </aside>
  <div class="s02-main">
   <header class="s02-topbar">
    <nav class="s02-breadcrumb" aria-label="当前工作"><span>Engineering / Fall</span><i>›</i><span>Signals Lab</span><i>›</i><strong>Filter response</strong></nav>
    <span class="s02-connection"><i></i>未连接 · 静态骨架</span>
   </header>
   <div class="s02-workbar">
    <nav class="s02-work-tabs" aria-label="工作区页签">
     <span class="selected" aria-current="page">${icon('file-text',18)}Source</span>
     <span>${icon('file-text',18)}Report</span>
     <span>${icon('history',18)}Run history</span>
    </nav>
    <div class="s02-work-actions"><button class="s02-export" disabled title="骨架阶段：导出尚未接入">${icon('download',17)}Export report</button>${tool('ellipsis-vertical','更多操作')}</div>
   </div>
   <main class="s02-panels" aria-label="原材料、报告与运行三栏">
    <section class="s02-pane s02-source" aria-labelledby="s02-source-title">
     <header class="s02-filebar"><span class="s02-filetab"><span class="s02-pdf-icon">${icon('file-text',17)}</span><span id="s02-source-title">Lab03_brief.pdf</span>${tool('x','关闭原材料')}</span>${tool('x','关闭阅读面板')}</header>
     <div class="s02-document-tools"><div class="s02-page-controls">${tool('arrow-left','上一页')}<span class="s02-page-field">— / —</span>${tool('arrow-right','下一页')}</div><span class="s02-zoom">100% ${icon('chevron-down',13)}</span>${tool('search','搜索原材料')}${tool('maximize-2','展开原材料')}</div>
     <div class="s02-pane-body s02-reader"><div class="s02-paper" id="s02-source-slot"><p class="s02-placeholder">原材料阅读区域<small>第 03 步接入正文 / PDF</small></p></div></div>
    </section>
    <section class="s02-pane s02-report" aria-labelledby="s02-report-title">
     <header class="s02-filebar"><span class="s02-filetab">${icon('file-text',17)}<span id="s02-report-title">report.md</span>${tool('x','关闭报告')}</span></header>
     <div class="s02-report-tools"><span class="selected">${icon('book-open',15)}Preview</span><span>${icon('code',15)}Raw</span><small>尚未生成报告</small></div>
     <div class="s02-pane-body s02-report-body" id="s02-report-slot"><p class="s02-placeholder">报告内容区域<small>第 04 步接入预览 / 原文 / 导出</small></p></div>
    </section>
    <aside class="s02-pane s02-run" aria-labelledby="s02-run-title">
     <h1 id="s02-run-title">This run</h1>
     <div class="s02-run-slot" id="s02-run-slot"><p class="s02-placeholder">步骤时间线区域<small>第 05 步接入真实运行状态</small></p></div>
     <div class="s02-current-slot">当前步骤与动作<small>尚未接入执行器</small></div>
     <div class="s02-preserved-slot">${icon('folder',20)}<div>文件保留状态<small>尚未核对文件</small></div></div>
    </aside>
   </main>
   <footer class="s02-statusbar"><span>第 02 步 · 结构预览 · 示例文件名</span><span>阅读、报告和执行功能均未接入</span></footer>
  </div>
 </div>`;
}
