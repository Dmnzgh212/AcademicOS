import test from 'node:test';
import assert from 'node:assert/strict';
import {platformReferenceState} from '../ui/reference-state.js';
import {libraryModel,renderLibrary} from '../ui/library.js';
import {sourceModel,renderSources,renderUpdates} from '../ui/sources.js';
import {resourceModel,renderCatalog,renderProjectResources} from '../ui/resources.js';
import {monitorModel,renderMonitor} from '../ui/monitor.js';
import {createWorkbench} from '../ui/workbench.js';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const btn=(action,text,id='',primary=false)=>`<button class="button ${primary?'primary':''}" data-action="${action}" data-id="${esc(id)}">${text}</button>`;
test('library filter excludes stale selection from another course; valid historical selection keeps versions and work references',()=>{
 const s=platformReferenceState(),m=libraryModel(s,{scope:'ELG2138',category:'labs',selected:'sample-brief-v1'});assert.equal(m.doc.id,'sample-brief-v1');assert.equal(m.versions.length,2);assert.ok(m.works.some(r=>r.id==='sample-work'));
 assert.equal(libraryModel(s,{scope:'robotics',selected:'sample-brief-v1'}).doc,undefined);assert.equal(libraryModel(s,{query:'measurements',selected:'sample-brief'}).doc.id,'measure');
 assert.equal(libraryModel(s,{scope:'signals',selected:'sample-brief'}).docs.length,1);assert.equal(libraryModel(s,{change:'new'}).docs[0].id,'announcement');
 const html=renderLibrary(s,{scope:'ELG2138',selected:'sample-brief-v1'},{esc,btn});assert.match(html,/历史版本/);assert.match(html,/sample-work/);assert.match(html,/正在核对/);assert.ok(!html.includes('已核对保存'));
});
test('failed source checks preserve the valid document and are not described as no change or success',()=>{
 const s=platformReferenceState();s.checks.push({id:'failure',sourceId:'elg-source',time:'2026-10-12T20:00:00Z',status:'failed',error:'Login expired'});
 const m=sourceModel(s,{scope:'ELG2138',selected:'elg-source'});assert.equal(m.check.status,'failed');assert.equal(m.doc.id,'sample-brief');
 const html=renderSources(s,{scope:'ELG2138'},{esc,btn});assert.match(html,/Login expired/);assert.match(html,/检查失败/);assert.match(html,/source-pipeline/);
 const changes=renderUpdates(s,{scope:'ELG2138'},{esc,btn});assert.match(changes,/sample-brief/);assert.ok(!changes.includes('csi-source'));
});
test('resource inspector distinguishes current-run fixed versions from the next selection and exposes each newer version',()=>{
 const s=platformReferenceState(),run=s.runs.find(r=>r.id==='sample-run');s.projectResources.signals[0].version='2';
 const model=resourceModel(s,'signals',run);assert.equal(model[0].using.version,'2');assert.equal(model[0].frozen.version,'1');assert.equal(model.filter(r=>r.update).length,1);
 const html=renderProjectResources(s,'signals',run,{esc,btn});assert.match(html,/本次固定 v1/);assert.match(html,/下次使用 v2/);assert.match(html,/v4 可更新/);
 const catalog=renderCatalog(s,{selected:'explain',version:'1'},{esc,btn});assert.match(catalog,/data-id="explain::1"/);assert.match(catalog,/sample-run/);
});
test('browser view uses one inspector; frozen frames cannot imply a live connection or leak another target/run',()=>{
 const s=platformReferenceState(),target={id:'sample-target',url:'https://example.com/elg2138',owner:'user',status:'paused'},run=s.runs.find(r=>r.id==='collect-run'),options={target:target.id,targets:[target],data:{target,image:'YWJj',capturedAt:'2026-10-12T14:00:00Z',events:[]},error:'Disconnected',run,inspector:'run',tab:'live'};
 const m=monitorModel(s,options);assert.equal(m.run.id,'collect-run');assert.ok(m.docs.every(d=>d.sourceId==='elg-source'));
 const html=renderMonitor(s,options,{esc,btn});assert.equal((html.match(/class="monitor-inspector /g)||[]).length,1);assert.match(html,/已冻结，非实时画面/);assert.match(html,/交回并检查/);assert.match(html,/控制权已交给你/);
 const other=monitorModel(s,{...options,target:'different',targets:[{id:'different',owner:'system'}]});assert.equal(other.data,null);assert.equal(other.run,null);assert.equal(other.docs.length,0);
 const wb=createWorkbench({getState:()=>s,esc,btn,asset:()=>'',runId:()=>'',draft:()=>null,station:{render:route=>route==='monitor'?html:''}});assert.equal(wb.render('monitor'),html);assert.ok(!wb.render('monitor').includes('workspace-stage'));
});
test('collection and browser/resource rendering escape labels and original HTML without mutating host records',()=>{
 const s=platformReferenceState();s.docs[0].name='<img src=x>';s.documentTexts[s.docs[0].id]='<script>bad()</script>';s.sources[0].url='javascript:alert(1)';s.resourceCatalog[0].name='<svg onload=alert(1)>';const before=JSON.stringify(s);
 for(const html of [renderLibrary(s,{selected:'sample-brief'},{esc,btn}),renderSources(s,{}, {esc,btn}),renderCatalog(s,{}, {esc,btn})]){assert.ok(!html.includes('<img src=x>'));assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<svg onload'));assert.ok(!html.includes('href="javascript:'));}
 assert.equal(JSON.stringify(s),before);
});
