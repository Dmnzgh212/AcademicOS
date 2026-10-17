import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,renameSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {saveWorkDraft} from '../domain/work-drafts.js';
import {createRunCommandController} from '../adapters/run-command-controller.js';
import {RUN_LIMITS} from '../domain/run-commands.js';

const stamp='2026-10-16T01:30:00.000Z';
const code=expected=>error=>error.code===expected;
function host(t){
  const dir=mkdtempSync(join(tmpdir(),'lifehub-run-command-')),path=join(dir,'workspace.json');
  t.after(()=>rmSync(dir,{recursive:true,force:true}));
  let state={projects:[{id:'course'},{id:'project'},{id:'other'}],requests:[],runs:[],sources:[],
    docs:[{id:'v1',projectId:'course',materialId:'lecture',version:1,name:'lecture.txt',size:15,type:'text/plain',supersededBy:'v2'},
      {id:'v2',projectId:'course',materialId:'lecture',version:2,name:'lecture.txt',size:15,type:'text/plain'}],
    libraryRefs:[{projectId:'project',materialId:'lecture'}],documentTexts:{v1:'SECRET_BODY_OLD',v2:'SECRET_BODY_NEW'},
    projectResources:{project:[{resourceId:'method',version:'1'}]},
    resourceCatalog:[{id:'method',name:'Index',kind:'method',versions:[{version:'1',body:'SECRET_METHOD_V1'}]}]};
  state=saveWorkDraft(state,{contextId:'project',draft:{title:'Index lecture',goal:'List source headings.',mode:'organize',docIds:['v1']}},
    {makeId:()=> 'work-1',now:()=>stamp}).state;
  writeFileSync(path,JSON.stringify(state));
  let writes=0,failSave=false,serial=0;
  const commit=fn=>{
    const before=structuredClone(state);
    try{fn();if(failSave)throw Error('C:/private/credentials/quota');
      writeFileSync(path+'.tmp',JSON.stringify(state));renameSync(path+'.tmp',path);writes++;return true;
    }catch{state=before;return false;}
  };
  const controller=()=>createRunCommandController({getState:()=>state,commit,makeId:kind=>`${kind}-${++serial}`,now:()=>stamp});
  const command=(extra={})=>({contextId:'project',commandId:'cmd-1',workId:'work-1',expectedRevision:1,
    inputVersionIds:['v1'],resourceRefs:[{resourceId:'method',version:'1'}],...extra});
  return {state:()=>state,controller,command,path,writes:()=>writes,reopen:()=>{state=JSON.parse(readFileSync(path,'utf8'));},
    fail:value=>{failSave=value;}};
}

test('admission persists a queued snapshot and accepted event; reopen/query never invent execution',t=>{
  const h=host(t),controller=h.controller(),receipt=controller.accept(h.command());
  assert.equal(receipt.status,'accepted');assert.equal(receipt.replayed,false);assert.equal(h.writes(),1);
  h.reopen();const view=h.controller().get({contextId:'project',runId:receipt.runId,limit:1});
  assert.equal(view.status,'queued');assert.ok(view.steps.every(step=>step.status==='pending'));
  assert.deepEqual(view.events.map(event=>[event.seq,event.kind]),[[1,'accepted']]);
  assert.equal(view.lastSeq,1);assert.equal(view.nextSeq,1);assert.equal(view.inputScopeAvailable,true);
  assert.deepEqual(h.state().runs[0].artifactIds,[]);assert.deepEqual(h.state().runs[0].materials,[]);
  assert.ok(!JSON.stringify(view).includes('SECRET_BODY'));assert.ok(!JSON.stringify(view).includes('SECRET_METHOD'));
  assert.deepEqual(controller.get({contextId:'project',runId:receipt.runId,afterSeq:1}).events,[]);
  assert.throws(()=>controller.get({contextId:'project',runId:receipt.runId,afterSeq:2}),code('INVALID_CURSOR'));
  assert.throws(()=>controller.get({contextId:'project',runId:receipt.runId,limit:0}),code('INVALID_CURSOR'));
  h.state().runs[0].events[0].seq=2;
  assert.throws(()=>controller.get({contextId:'project',runId:receipt.runId}),code('INVALID_STATE'));
});

test('same command replays after reopen and later edits without writing or allocating another run/event',t=>{
  const h=host(t),first=h.controller().accept(h.command());h.reopen();
  h.state().requests[0].goal='Changed afterwards';h.state().requests[0].revision=2;
  h.state().projectResources.project=[{resourceId:'method',version:'2'}];
  const retry=h.controller().accept(h.command());
  assert.equal(retry.runId,first.runId);assert.equal(retry.acceptedAt,first.acceptedAt);assert.equal(retry.replayed,true);
  assert.equal(h.writes(),1);assert.equal(h.state().runs.length,1);assert.equal(h.state().runCommands.length,1);
  assert.equal(h.state().runs[0].events.length,1);
});

test('reusing an ID for changed payload conflicts; another project cannot read the receipt/run',t=>{
  const h=host(t),controller=h.controller(),first=controller.accept(h.command());
  assert.throws(()=>controller.accept(h.command({expectedRevision:2})),code('COMMAND_CONFLICT'));
  assert.throws(()=>controller.accept(h.command({inputVersionIds:['v2']})),code('COMMAND_CONFLICT'));
  assert.throws(()=>controller.get({contextId:'other',runId:first.runId}),code('UNAVAILABLE'));
  assert.throws(()=>controller.accept(h.command({contextId:'other'})),code('UNAVAILABLE'));
  assert.equal(h.writes(),1);
});

test('work/input/resource snapshots stay fixed; unknown credentials and caller receipt edits are not persisted',t=>{
  const h=host(t),state=h.state();state.requests[0].authorization='DO_NOT_COPY';state.docs[0].cookie='DO_NOT_COPY';
  const receipt=h.controller().accept(h.command()),runId=receipt.runId;
  state.requests[0].goal='edited';state.docs[0].name='edited';state.documentTexts.v1='edited';
  state.resourceCatalog[0].versions[0].body='edited';receipt.runId='consumer-edit';
  const run=state.runs[0];
  assert.equal(run.request.goal,'List source headings.');assert.equal(run.workRevision,1);
  assert.equal(run.docs[0].name,'lecture.txt');assert.equal(run.docs[0].version,1);
  assert.equal(run.manualTexts.v1,'SECRET_BODY_OLD');assert.equal(run.resources[0].body,'SECRET_METHOD_V1');
  assert.ok(!JSON.stringify(run).includes('DO_NOT_COPY'));assert.equal(state.runCommands[0].runId,runId);
});

test('failed storage returns no accepted receipt; restored retry saves one run and one command',t=>{
  const h=host(t),before=readFileSync(h.path,'utf8');h.fail(true);
  assert.throws(()=>h.controller().accept(h.command()),error=>error.code==='SAVE_FAILED'&&!error.message.includes('private'));
  assert.equal(readFileSync(h.path,'utf8'),before);assert.equal(h.state().runs.length,0);assert.equal(h.state().runCommands,undefined);
  h.fail(false);const receipt=h.controller().accept(h.command());h.reopen();
  assert.equal(h.controller().accept(h.command()).runId,receipt.runId);
  assert.equal(h.state().runs.length,1);assert.equal(h.state().runCommands.length,1);assert.equal(h.writes(),1);
});

test('stale work, missing inputs, changed selection and nonlocal modes are rejected before persistence',t=>{
  const cases=[
    [h=>h.command({expectedRevision:2}),'REVISION_CONFLICT'],
    [h=>h.command({inputVersionIds:['v2']}),'INPUT_CONFLICT'],
    [h=>{h.state().requests[0].docIds=[];return h.command({inputVersionIds:[]});},'INPUT_REQUIRED'],
    [h=>h.command({resourceRefs:[]}),'RESOURCE_CONFLICT'],
    [h=>{h.state().requests[0].mode='learn';return h.command();},'UNSUPPORTED_WORK'],
    [h=>{h.state().sources.push({id:'portal',projectId:'project'});h.state().requests[0].sourceIds=['portal'];return h.command();},'UNSUPPORTED_WORK'],
    [h=>h.command({inputVersionIds:['v1','v1']}),'INVALID_COMMAND']
  ];
  for(const [prepare,expected] of cases){const h=host(t),command=prepare(h);assert.throws(()=>h.controller().accept(command),code(expected));
    assert.equal(h.writes(),0);assert.equal(h.state().runs.length,0);}
});

test('revoked input scope is visible in history; a fresh command cannot bypass the removed reference',t=>{
  const h=host(t),first=h.controller().accept(h.command());h.state().libraryRefs=[];
  const view=h.controller().get({contextId:'project',runId:first.runId});
  assert.equal(view.inputScopeAvailable,false);assert.equal(view.status,'queued');assert.equal(view.events[0].kind,'accepted');
  assert.ok(!JSON.stringify(view).includes('SECRET_BODY'));
  assert.throws(()=>h.controller().accept(h.command({commandId:'cmd-new'})),code('INPUT_REQUIRED'));
  assert.equal(h.writes(),1);
});

test('snapshot/capacity limits reject without dropping older idempotency records',t=>{
  const h=host(t);h.state().documentTexts.v1='x'.repeat(RUN_LIMITS.textChars+1);
  assert.throws(()=>h.controller().accept(h.command()),code('TOO_LARGE'));assert.equal(h.writes(),0);
  h.state().documentTexts.v1='small';h.state().resourceCatalog[0].versions[0].body='x'.repeat(12001);
  assert.throws(()=>h.controller().accept(h.command()),code('INVALID_RESOURCE'));assert.equal(h.writes(),0);
  h.state().resourceCatalog[0].versions[0].body='method';const receipt=h.controller().accept(h.command());
  h.state().runCommands.push(...Array.from({length:RUN_LIMITS.commands-1},(_,i)=>({contextId:'project',commandId:`other-${i}`})));
  assert.equal(h.controller().accept(h.command()).runId,receipt.runId);
  assert.throws(()=>h.controller().accept(h.command({commandId:'capacity-new'})),code('CAPACITY'));
  assert.equal(h.state().runCommands.length,RUN_LIMITS.commands);assert.equal(h.state().runs.length,1);assert.equal(h.writes(),1);
});
