import {platformReferenceState} from './reference-state.js';
import {navigation,breadcrumbs} from './shell.js';
import {createWorkbench} from './workbench.js';
import {renderSchedule} from './schedule.js';
import {renderLibrary} from './library.js';
import {renderSources,renderUpdates} from './sources.js';
import {renderCatalog} from './resources.js';
import {renderMonitor} from './monitor.js';
import {icon} from './icons.js';
const state=platformReferenceState(),schedule={mode:'week',offset:0,scope:'',weekend:false,clock:{date:'2026-10-12',time:'09:00'}},library={scope:'ELG2138',category:'labs',query:'',status:'',change:'',selected:'sample-brief',originals:Object.fromEntries(state.docs.map(d=>[d.id,true]))},catalog={selected:'explain',kind:'',version:'',updates:false},sources={scope:'',selected:''};
let asset='doc:sample-brief-v1',runId='sample-run',monitorTab='live',monitorInspector='run',owner='system';
const $=id=>document.getElementById(id),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const btn=(a,label,id='',primary=false)=>`<button class="button ${primary?'primary':''}" data-action="${a}" ${id?`data-id="${esc(id)}"`:''}>${label}</button>`;
const modal=(title,body)=>{$('dialog-title').textContent=title;$('dialog-body').innerHTML=body;if(!$('dialog').open)$('dialog').showModal();};
const route=()=>location.hash.slice(1)||'work';
const wb=createWorkbench({getState:()=>state,esc,btn,modal,change:fn=>{fn();render();return true;},go:r=>{location.hash='#'+r;render();},toast:()=>{},fileOp:async(_,id)=>new Blob([state.documentTexts[id]||''],{type:'text/markdown'}),render,station:{render:()=>''},asset:()=>asset,runId:()=>runId,selectAsset:x=>asset=x,selectRun:x=>runId=x,draft:()=>null});
function monitorOptions(){const target={id:'sample-target',title:'Course portal · 布局样例',url:'https://example.com/elg2138',owner,status:owner==='system'?'ready':'paused'};return {target:target.id,targets:[target],data:{target,capturedAt:'2026-10-12T14:42:09Z',events:[{time:'2026-10-12T14:42:06Z',message:'示例：找到 Lab 03 目录'},{time:'2026-10-12T14:42:09Z',message:owner==='user'?'示例：用户接管，自动动作暂停':'示例：等待读取选定范围'}]},error:'',run:state.runs.find(r=>r.id==='collect-run'),tab:monitorTab,inspector:monitorInspector};}
function portal(){return `<div class="reference-portal"><div class="reference-portal-label">示例页面 · 非真实浏览器画面</div><header>${icon('book-open',24)}<strong>Course portal</strong><span>课程　日程　资源</span></header><div class="reference-portal-body"><p>Content / Lab 03</p><h1>ELG2138 · Signals Lab</h1><nav>Home　 Syllabus　 <strong>Content</strong>　 Assignments　 Grades</nav><h2>${owner==='user'?'Choose source folder':'Lab 03 — Frequency Response of Filters'}</h2>${owner==='user'?'<div class="reference-source-choice"><strong>◉ Lab 03 — Current</strong><p>本学期材料 · 示意选择</p><strong>○ Lab 03 — Archive</strong></div>':''}<table class="collection-table"><thead><tr><th>文件</th><th>类型</th><th>更新</th></tr></thead><tbody>${[['sample-brief','Lab03_brief.md','Lab brief'],['measure','measurements.csv','CSV'],['script','filter_design.py','Python']].map(([id,name,type])=>`<tr><td><button data-action="station-open-doc" data-id="${id}">${icon(type==='Python'?'code':'file-text',17)}${name}</button></td><td>${type}</td><td>10/12 · 示例</td></tr>`).join('')}</tbody></table><h2>Lab Description</h2><p>Implement a filter, compare theoretical and illustrative response curves, and explain differences. This is layout sample content.</p></div></div>`;}
function curves(){return ['Low-pass response','High-pass response'].map((title,i)=>{const x=f=>32+(Math.log10(f)-1)/3*210,y=v=>110-Math.max(-40,20*Math.log10(Math.max(0.001,v)))*2.5;const points=Array.from({length:70},(_,n)=>{const f=10**(1+n/69*3),gain=i?(f/350)/Math.sqrt(1+(f/350)**2):1/Math.sqrt(1+(f/350)**2);return `${x(f).toFixed(2)},${(y(gain)-65).toFixed(2)}`;}).join(' ');return `<figure><figcaption>${title}</figcaption><svg viewBox="0 0 270 180" role="img" aria-label="Analytical sample filter curve"><g stroke="#e1e7df" stroke-width="1">${[0,1,2,3,4,5].map(n=>`<path d="M32 ${45+n*20}H242"/>`).join('')}${[0,1,2,3].map(n=>`<path d="M${32+n*70} 45V145"/>`).join('')}</g><path d="M32 45V145H242" fill="none" stroke="#a2ada0"/><polyline points="${points}" fill="none" stroke="#2e7f60" stroke-width="1.8"/><g fill="#88937f" font-size="9" font-family="Segoe UI,sans-serif"><text x="15" y="49">0</text><text x="6" y="99">−20</text><text x="6" y="149">−40</text><text x="29" y="159">10</text><text x="90" y="159">100</text><text x="156" y="159">1k</text><text x="227" y="159">10k</text><text x="106" y="176">Frequency (Hz)</text></g></svg></figure>`;}).join('');}
function render(){
 const current=route(),browser=['monitor','takeover','resources'].includes(current),active=browser?'monitor':current,global=['schedule','library','sources','updates','catalog'].includes(active);wb.cancel();
 if(browser)state.currentProject='ELG2138';
 $('global-nav').innerHTML=navigation(state,active,esc).replace(/href="#([^" ]+)"/g,'href="#$1"');
 $('crumb').innerHTML=breadcrumbs(state,{run:browser?state.runs.find(r=>r.id==='collect-run'):wb.model().run,route:active},esc);
 document.querySelectorAll('.reference-views a').forEach(a=>a.classList.toggle('active',a.hash==='#'+current));
 $('main').className=global?'global-page':'workspace-main';
 if(active==='schedule')$('main').innerHTML=renderSchedule(state,schedule,{esc,btn});
 else if(active==='library')$('main').innerHTML=renderLibrary(state,library,{esc,btn});
 else if(active==='sources')$('main').innerHTML=renderSources(state,sources,{esc,btn});
 else if(active==='updates')$('main').innerHTML=renderUpdates(state,sources,{esc,btn});
 else if(active==='catalog')$('main').innerHTML=renderCatalog(state,catalog,{esc,btn});
 else if(browser){$('main').innerHTML=renderMonitor(state,monitorOptions(),{esc,btn});$('monitor-state').textContent='布局样例 · 非实时连接';if(monitorTab==='live')$('monitor-picture').innerHTML=portal();}
 else{$('main').innerHTML=wb.render(['work','report','history'].includes(active)?active:'work');wb.mount();const article=$('main').querySelector('.markdown-document');if(article&&article.querySelector('h2')){const plots=document.createElement('div');plots.className='reference-curves';plots.innerHTML=curves();article.querySelector('h2').insertAdjacentElement('afterend',plots);}}
}
function navigate(r){location.hash='#'+r;render();}
function chooseWork(id){const work=state.requests.find(x=>x.id===id);if(!work)return;state.currentProject=work.projectId;wb.contextChanged();runId=state.runs.find(x=>x.requestId===id)?.id||'';asset='';wb.selectWork(id);navigate('work');}
function handoff(r='work'){modal('独立布局样例',`<p class="notice">这些是示例数据，没有执行真实采集、脚本或浏览器动作。请进入个人工作区操作真实记录。</p><a class="button primary" href="https://lifehub-workstation.zhihangz212.chatgpt.site/#${r}">打开个人工作区</a>`);}
document.addEventListener('click',async e=>{
 const el=e.target.closest('[data-action]');if(!el)return;const {action:a,id}=el.dataset;e.preventDefault();
 if(a==='close-dialog'){$('dialog').close();return;}
 if(a==='reference-screen'){if(id==='work'){state.currentProject='signals';runId='sample-run';asset='doc:sample-brief-v1';wb.contextChanged();}if(id==='takeover'){owner='user';monitorInspector='run';}else if(id==='resources'){owner='system';monitorInspector='resources';}else if(id==='monitor'){owner='system';monitorInspector='run';}navigate(id);return;}
 if(a==='station-route'){navigate(id==='continue'?'schedule':id);return;}
 if(a==='station-week'){schedule.offset=id==='0'?0:schedule.offset+Number(id);render();return;}
 if(a==='station-schedule-mode'){schedule.mode=id;render();return;}
 if(a==='station-schedule-weekend'){schedule.weekend=!schedule.weekend;render();return;}
 if(a==='station-library-folder'){Object.assign(library,JSON.parse(id));library.selected='';render();return;}
 if(a==='station-library-scope'){library.scope=id;library.category='';library.selected='';render();return;}
 if(a==='station-select-doc'){library.selected=id;render();return;}
 if(a==='station-open-doc'){const d=state.docs.find(x=>x.id===id);state.currentProject=d.projectId;asset='doc:'+id;runId='';wb.contextChanged();navigate('work');return;}
 if(a==='station-open-request'){chooseWork(id);return;}
 if(a==='show-run'){chooseWork(state.runs.find(r=>r.id===id)?.requestId);return;}
 if(a==='station-context'){state.currentProject=id;asset='';runId='';wb.contextChanged();navigate('work');return;}
 if(a==='station-resource-select'||a==='station-resource-view'){catalog.selected=id;catalog.version='';if(a==='station-resource-view')navigate('catalog');else render();return;}
 if(a==='station-catalog-updates'){catalog.updates=!catalog.updates;catalog.selected='';navigate('catalog');return;}
 if(a==='station-source-select'){sources.selected=id;render();return;}
 if(a==='station-source-view'){sources.selected=id;navigate('sources');return;}
 if(a==='station-updates-scope'){sources.scope=id;navigate('updates');return;}
 if(a==='station-monitor-inspector'){monitorInspector=id;render();return;}
 if(a==='station-monitor-tab'){monitorTab=id;render();return;}
 if(a==='station-monitor-source'){owner='system';monitorInspector='run';navigate('monitor');return;}
 if(a==='station-control'){owner=id==='resume'?'system':id==='takeover'?'user':'paused';render();return;}
 if(a==='station-monitor-frame'||a==='station-open-browser'){handoff('monitor');return;}
 if(await wb.action(a,id))return;
 if(a==='download-artifact'){const artifact=state.artifacts.find(x=>x.id===id),url=URL.createObjectURL(new Blob([artifact.text],{type:'text/markdown'})),link=document.createElement('a');link.href=url;link.download='LifeHub-example-report.md';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;}
 if(a==='save-artifact'){state.artifacts.find(x=>x.id===id).text=$('artifact-editor').value;render();return;}
 if(a==='save-doc-text'){state.documentTexts[id]=$('doc-text-editor').value;$('dialog').close();render();return;}
 handoff(route()==='library'?'library':route()==='catalog'?'catalog':route()==='sources'?'sources':'work');
});
document.addEventListener('input',e=>{const el=e.target,name=el.name;
 if(name==='schedule-scope')schedule.scope=el.value;
 else if(el.id==='library-search'){library.query=el.value;clearTimeout(library.timer);const start=el.selectionStart;library.timer=setTimeout(()=>{render();const input=$('library-search');input?.focus();input?.setSelectionRange(start,start);},200);return;}
 else if(['library-category','library-status','library-change'].includes(name)){library[name.slice(8)]=el.value;library.selected='';}
 else if(name==='source-scope')sources.scope=el.value;
 else if(name==='catalog-kind'){catalog.kind=el.value;catalog.selected='';catalog.version='';}
 else if(name==='catalog-version')catalog.version=el.value;
 else{wb.input(el);return;}render();
});
window.addEventListener('hashchange',()=>{if(route()==='takeover'){owner='user';monitorInspector='run';}else if(route()==='resources'){monitorInspector='resources';owner='system';}render();});
if(route()==='takeover')owner='user';if(route()==='resources')monitorInspector='resources';render();
