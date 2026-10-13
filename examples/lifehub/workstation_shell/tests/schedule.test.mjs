import test from 'node:test';
import assert from 'node:assert/strict';
import {calendarLayout,scheduleModel,scheduleClock,renderSchedule} from '../ui/schedule.js';
import {scheduleReferenceState} from '../ui/reference-state.js';
import {createWorkbench} from '../ui/workbench.js';
const clock={date:'2026-10-12',time:'11:30'};
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const btn=(a,text,id='')=>`<button data-action="${a}" data-id="${esc(id)}">${text}</button>`;
const event=(id,start,end,date='2026-10-12')=>({id,title:id,projectId:'CSI2110',date,start,end});
test('connected overlap groups keep concurrent events in distinct lanes and adjacent periods reuse a lane',()=>{
 const events=[event('a','10:00','11:00'),event('b','10:30','12:00'),event('c','11:00','11:30'),event('d','12:00','13:00')],out=calendarLayout(events);
 for(const a of out)for(const b of out){if(a.id!==b.id&&a.startMinute<b.endMinute&&b.startMinute<a.endMinute)assert.notEqual(a.lane,b.lane);}
 assert.equal(out.find(e=>e.id==='a').lane,out.find(e=>e.id==='c').lane);assert.equal(out.find(e=>e.id==='d').lanes,1);assert.equal(out.find(e=>e.id==='b').lanes,2);
});
test('weekend and early/late events expand the visible grid; offset and project filters preserve originals',()=>{
 const s=scheduleReferenceState();s.events.push(event('early','06:15','07:00','2026-10-17'),event('late','22:00','23:45'));const before=JSON.stringify(s);
 const m=scheduleModel(s,{clock});assert.equal(m.days.length,7);assert.equal(m.start,360);assert.equal(m.end,1440);assert.ok(m.events.some(e=>e.id==='early'));
 const filtered=scheduleModel(s,{clock,scope:'signals'});assert.equal(filtered.days.length,5);assert.deepEqual(filtered.events.map(e=>e.id),['signals-plan']);
 assert.equal(scheduleModel(s,{clock,offset:1}).week[0],'2026-10-19');assert.equal(JSON.stringify(s),before);
});
test('upcoming removes ended events, retains an ongoing event, and scopes work plus source updates consistently',()=>{
 const s=scheduleReferenceState();s.events.push(event('ongoing','11:00','12:00'));s.runs.push({id:'new-lab',requestId:'lab-work',status:'completed',created:'2026-10-12T13:00:00Z'});
 const m=scheduleModel(s,{clock,scope:'CSI2110'});assert.ok(!m.upcoming.some(e=>e.id==='lecture-mon'));assert.equal(m.upcoming[0].id,'ongoing');assert.equal(m.work.length,0);assert.deepEqual(m.checks.map(c=>c.sourceId),['csi-source']);
 assert.equal(scheduleModel(s,{clock,scope:'robotics'}).work[0].status,'queued');
});
test('Toronto clock respects date rollover and daylight saving without using the browser local timezone',()=>{
 assert.deepEqual(scheduleClock(new Date('2026-10-12T02:00:00Z')),{date:'2026-10-11',time:'22:00'});
 assert.deepEqual(scheduleClock(new Date('2026-11-02T05:15:00Z')),{date:'2026-11-02',time:'00:15'});
});
test('render uses duration geometry and actual work IDs, escapes user labels and rejects unsafe source links',()=>{
 const s=scheduleReferenceState();s.events[0].title='<img src=x onerror=alert(1)>';s.sources[0].url='javascript:alert(1)';s.checks[0].status='failed';
 const html=renderSchedule(s,{clock:{date:'2026-10-12',time:'09:00'}},{esc,btn});assert.match(html,/schedule-time-axis/);assert.match(html,/height:78px/);assert.match(html,/data-id="lab-work"/);assert.match(html,/接续工作/);assert.match(html,/检查失败/);assert.ok(!html.includes('<img'));assert.ok(!html.includes('href="javascript:'));assert.ok(!html.includes('Sources checked just now'));
 const agenda=renderSchedule(s,{clock,mode:'agenda',scope:'signals'},{esc,btn});assert.match(agenda,/schedule-agenda-row/);assert.match(agenda,/sample-work/);assert.ok(!agenda.includes('lab-work'));
 for(const work of s.requests){s.currentProject=work.projectId;const run=s.runs.find(r=>r.requestId===work.id);const wb=createWorkbench({getState:()=>s,esc,btn,asset:()=>'',runId:()=>run?.id||'',draft:()=>null,station:{render:()=>''}});assert.match(wb.render(),/source-pane/);}
});
