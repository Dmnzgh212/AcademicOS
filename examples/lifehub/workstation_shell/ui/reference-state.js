// Isolated visual fixture. Never stored in the user's workspace or used as execution evidence.
export function referenceState(){
 const text='# Compare theory and measurements\n\nLab 03 — Frequency Response of Filters\n\n## 1 Objective\n\nIn this lab you will implement a discrete-time filter and compare its theoretical response with an illustrative response.\n\n## 2 Procedure\n\n1. Implement the given filter in Python or MATLAB.\n2. Excite the system with a swept-sine input.\n3. Compute the theoretical frequency response.\n4. Compare the response curves and explain differences.\n\n## 3 Deliverables\n\n> Include a response plot, document the source files, and explain the reasoning.\n\nThis is a layout sample; it is not an actual course requirement.';
 const report='# Frequency response\n\nThis sample report demonstrates how the result remains beside its source material. It contains no user measurements.\n\n## Response comparison\n\nTwo illustrative filter curves appear below. These are computed from simple analytical functions for layout inspection.\n\n## Source files\n\n- **Lab03_brief.md** — illustrative assignment requirements\n- **measurements.csv** — sample file name\n- **filter_design.py** — sample script name\n\n## Interpretation\n\nThe report and the original material are separate. Future runs keep their own inputs and results.';
 return {version:1,currentProject:'signals',projects:[{id:'signals',name:'Signals Lab',kind:'project',term:'Engineering / Fall'},{id:'robotics',name:'Robotics',kind:'project'},{id:'algorithms',name:'Algorithms',kind:'project'}],checks:[],libraryRefs:[],docs:[{id:'sample-brief',materialId:'sample-brief',projectId:'signals',name:'Lab03_brief.md',version:1,category:'labs',size:new Blob([text]).size,type:'text/markdown',date:'2026-10-11'}],documentTexts:{'sample-brief':text},sources:[],requests:[{id:'sample-work',projectId:'signals',title:'Filter response',goal:'Read the example and compare response curves.',mode:'learn',docIds:['sample-brief'],sourceIds:[]}],runs:[{id:'sample-run',projectId:'signals',requestId:'sample-work',title:'Filter response',mode:'learn',status:'paused',cursor:3,message:'示例状态：等待继续。',created:'2026-10-11T18:00:00Z',docs:[{id:'sample-brief'}],steps:[{key:'scope',label:'确认材料范围',status:'done'},{key:'read',label:'读取原材料',status:'done'},{key:'prepare',label:'整理报告内容',status:'done'},{key:'chat',label:'取得聊天回复',status:'pending'},{key:'save',label:'保存报告',status:'pending'}],artifactIds:['sample-report'],events:[]}],artifacts:[{id:'sample-report',projectId:'signals',runId:'sample-run',title:'report.md',kind:'示例报告',text:report}],projectResources:{signals:[]},resourceCatalog:[]};
}

// Fixed dates keep the isolated slide-1 fixture reproducible.
export function scheduleReferenceState(){
 const s=referenceState();s.requests[0].created='2026-10-11T18:00:00Z';
 s.projects.unshift(...['CSI2110','ELG2138','CEG2136'].map(id=>({id,name:id,kind:'course',term:'Fall 2026'})));
 s.sources=[{id:'csi-source',projectId:'CSI2110',name:'CSI2110 · 课程公告',url:'https://example.com/csi2110'},{id:'elg-source',projectId:'ELG2138',name:'ELG2138 · Lab',url:'https://example.com/elg2138'},{id:'ceg-source',projectId:'CEG2136',name:'CEG2136 · Tutorial',url:'https://example.com/ceg2136'}];
 s.requests.unshift({id:'lab-work',projectId:'CSI2110',title:'Lab 3 preparation',goal:'示例：准备实验材料。',mode:'learn',docIds:[],sourceIds:[],created:'2026-10-12T11:00:00Z'},{id:'robot-work',projectId:'robotics',title:'Sensor prototype',goal:'示例：查看原型进展。',mode:'organize',docIds:[],sourceIds:[],created:'2026-10-10T12:00:00Z'});
 s.runs.unshift({id:'lab-run',projectId:'CSI2110',requestId:'lab-work',title:'Lab 3 preparation',status:'waiting',created:'2026-10-12T11:00:00Z',cursor:0,steps:[{label:'等待读取材料',status:'waiting'}],message:'布局样例状态。',artifactIds:[],events:[],docs:[]});
 s.events=[
  ['lecture-mon','CSI2110','CSI2110 · Lecture','2026-10-12','10:00','11:30','csi-source','lab-work'],
  ['lab-tue','ELG2138','ELG2138 · Lab','2026-10-13','14:00','16:00','elg-source',''],
  ['tutorial','CEG2136','CEG2136 · Tutorial','2026-10-14','12:00','13:30','ceg-source',''],
  ['lecture-thu','CSI2110','CSI2110 · Lecture','2026-10-15','16:00','17:30','csi-source','lab-work'],
  ['signals-plan','signals','Signals Lab analysis','2026-10-16','10:00','12:00','','sample-work'],
  ['robotics-plan','robotics','Robotics review','2026-10-16','16:00','18:00','','robot-work']
 ].map(([id,projectId,title,date,start,end,sourceId,requestId])=>({id,projectId,title,date,start,end,sourceId,requestId,kind:sourceId?'source':'personal',sourceText:sourceId?'示例时间原文；非真实课程要求。':''}));
 s.checks=[{id:'c1',sourceId:'csi-source',time:'2026-10-12T12:00:00Z',status:'changed',added:1,updated:0},{id:'c2',sourceId:'elg-source',time:'2026-10-12T10:00:00Z',status:'changed',added:0,updated:1}];
 s.tasks=[];return s;
}
