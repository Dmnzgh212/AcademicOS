import {icon} from './icons.js';
import {runStates,when} from './records.js';
import {renderProjectResources} from './resources.js';

// Connection records and frames are transient. Never infer progress from sample steps.
export function monitorModel(state,{target='',targets=[],data=null,error='',run=null}={}){
 const bound=targets.find(t=>t.id===target),fresh=data?.target?.id===target?data:null,t=fresh?{...bound,...fresh.target}:bound;
 const sources=state.sources.filter(s=>s.targetId===target),sourceIds=sources.map(s=>s.id);
 const linked=state.runs.find(r=>r.id===t?.workRunId)||(run&&(run.chatTarget===target||(run.sources||[]).some(s=>sourceIds.includes(s.id)))?run:null);
 const docs=state.docs.filter(d=>sourceIds.includes(d.sourceId)&&!d.supersededBy),events=fresh?.events||t?.events||[];
 return {target:t,data:fresh,error,run:linked,sources,docs,events,owner:t?.owner,status:t?.status,stale:!!error,canControl:!!t};
}
export function monitorControls(m,{btn}){
 if(!m.target)return btn('station-connect','连接浏览器');
 return `${m.owner==='user'||m.owner==='paused'||m.status==='stopped'?btn('station-control',icon('play',14)+'交回并检查','resume',true):btn('station-control',icon('pause',14)+'暂停','pause')}${m.owner!=='user'?btn('station-control',icon('external-link',14)+'接管','takeover'):''}${btn('station-control',icon('square',13)+'停止','stop')}`;
}
export function monitorRun(m,{esc,btn}){
 const run=m.run;
 return `<h2>本次运行</h2>${run?`<p class="monitor-run-name">${esc(run.title)} · ${runStates[run.status]||'待运行'}</p><ol class="run-timeline">${run.steps.map((s,i)=>`<li class="${esc(s.status)}" ${i===run.cursor?'aria-current="step"':''}><span class="timeline-dot">${s.status==='done'?icon('check',12):i+1}</span><div><strong>${esc(s.label)}</strong><small>${runStates[s.status]||'待执行'}</small></div></li>`).join('')}</ol>`:'<p class="collection-empty">当前页面没有关联到一项运行。下方显示这个绑定页面的实际动作记录。</p>'}<div class="monitor-inspector-divider"></div><h3>当前动作</h3><p class="monitor-current ${m.error?'failure':''}">${esc(m.error||m.events.at(-1)?.message||'等待页面操作')}</p>${m.owner==='user'?'<div class="monitor-handoff-note"><strong>控制权已交给你</strong><p>在原浏览器处理，准备好后交回。继续前会重新核对地址和页面状态。</p></div>':''}<div class="monitor-inspector-divider"></div><h3>已归档材料</h3>${m.docs.map(d=>btn('station-open-doc',icon('file-text',14)+esc(d.name)+' · v'+esc(d.version),d.id)).join('')||'<p class="collection-empty">此页面尚无有效归档。</p>'}${run?btn('show-run','查看运行记录',run.id):''}`;
}
export function monitorView(m,{esc,btn},tab='live'){
 if(tab==='history')return `<div class="monitor-action-history"><h2>页面动作历史</h2>${m.events.slice().reverse().map(e=>`<div><time>${when(e.time)}</time><p>${esc(e.message)}</p></div>`).join('')||'<p class="collection-empty">尚无动作记录。</p>'}</div>`;
 if(m.data?.image)return `<img src="data:image/jpeg;base64,${esc(m.data.image)}" alt="绑定页面预览${m.stale?'（已冻结，非实时画面）':''}">${m.stale?'<span class="monitor-frozen">画面已冻结</span>':''}`;
 return `<div class="monitor-empty">${icon('globe',40)}<h2>绑定页面实时预览</h2><p>${m.target?'在这个页面的扩展弹窗启用监控，然后开始预览。':'连接本地扩展并选择绑定页面，当前动作与归档结果会显示在右侧。'}</p>${m.target?btn('station-monitor-frame','开始预览','',true):btn('station-connect','连接本地浏览器','',true)}</div>`;
}
export function renderMonitor(state,options,{esc,btn}){
 const m=monitorModel(state,options),inspector=options.inspector==='resources'?'resources':'run';
 const select=`<select name="monitor-target" aria-label="选择绑定页面"><option value="">选择绑定页面</option>${options.targets.map(t=>`<option value="${esc(t.id)}" ${t.id===options.target?'selected':''}>${esc(t.title||t.url)}</option>`).join('')}</select>`;
 const control=m.status==='stopped'?'已停止':m.owner==='user'?'你正在控制 · 自动操作已暂停':m.owner==='paused'?'自动操作已暂停':m.target?'系统控制':'尚未连接';
 return `<div class="monitor-workspace" data-layout="ppt-browser" aria-label="运行监控"><div class="workspace-tabs"><nav aria-label="工作区视图">${[['work','file-text','原材料'],['report','file-text','产物'],['monitor','globe','浏览器'],['history','history','运行历史']].map(([id,glyph,title])=>`<a href="#${id}" class="${id==='monitor'?'active':''}">${icon(glyph)}${title}</a>`).join('')}</nav><div class="row monitor-primary-controls" id="monitor-controls">${monitorControls(m,{btn})}</div></div><div class="monitor-stage"><section class="monitor-canvas-column"><div class="monitor-browser-frame"><header class="monitor-browser-tab">${icon('globe',16)}${select}<span id="monitor-owner" class="${m.owner==='user'?'user-control':''}">${control}</span></header><div class="monitor-address"><span>${icon('link',14)}</span><output id="monitor-url">${esc(m.target?.url||'尚未选择页面')}</output>${btn('station-open-browser',icon('external-link',14)+'打开浏览器')}</div><div class="monitor-live-tools"><nav><button data-action="station-monitor-tab" data-id="live" class="${options.tab!=='history'?'active':''}">实时画面</button><button data-action="station-monitor-tab" data-id="history" class="${options.tab==='history'?'active':''}">动作历史</button></nav><span id="monitor-state">${m.error?'画面已冻结':m.data?'画面已连接':'尚未取得画面'}</span>${btn('station-monitor-frame','刷新画面')}</div><div id="monitor-handoff">${m.owner==='user'?'<div class="monitor-handoff-banner">在原浏览器继续处理，准备好后交回并检查。</div>':''}</div><div id="monitor-picture" class="monitor-picture">${monitorView(m,{esc,btn},options.tab)}</div><div id="monitor-footer" class="monitor-frame-footer">${m.data?'最后画面 '+when(m.data.capturedAt):'预览画面不保存到工作区'}${m.error?' · '+esc(m.error):''}</div></div><section class="monitor-recent collection-panel"><strong>最近动作</strong><div id="monitor-events">${m.events.slice(-3).map(e=>`<div><time>${when(e.time)}</time><span>${esc(e.message)}</span></div>`).join('')||'<p>尚无页面动作记录。</p>'}</div></section></section><aside class="monitor-inspector collection-panel"><div class="inspector-tabs"><button data-action="station-monitor-inspector" data-id="run" class="${inspector==='run'?'active':''}">本次运行</button><button data-action="station-monitor-inspector" data-id="resources" class="${inspector==='resources'?'active':''}">项目资源</button></div><div id="monitor-inspector-body">${inspector==='resources'?renderProjectResources(state,state.currentProject,m.run,{esc,btn}):monitorRun(m,{esc,btn})}</div></aside></div></div>`;
}
