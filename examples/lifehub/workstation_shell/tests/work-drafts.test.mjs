import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,renameSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createWorkDraftController} from '../adapters/work-draft-controller.js';
import {createMaterialReader} from '../adapters/material-reader.js';

const clock='2026-10-15T23:50:00.000Z';
const draft=(extra={})=>({title:'Lecture review',goal:'Explain the original lecture.',deliverable:'Notes with source references',mode:'learn',docIds:[],sourceIds:[],...extra});
const code=expected=>error=>error.code===expected;
function host(t){
  const dir=mkdtempSync(join(tmpdir(),'lifehub-work-draft-')),path=join(dir,'workspace.json');
  t.after(()=>rmSync(dir,{recursive:true,force:true}));
  let state={projects:[{id:'course'},{id:'project'},{id:'other'}],requests:[],
    docs:[{id:'v1',projectId:'course',materialId:'lecture',version:1,name:'lecture.txt',supersededBy:'v2'},
      {id:'v2',projectId:'course',materialId:'lecture',version:2,name:'lecture.txt'}],
    libraryRefs:[{projectId:'project',materialId:'lecture'}],sources:[{id:'portal',projectId:'course'}],
    runs:[{id:'existing-run',request:{goal:'Old running requirement'},status:'paused'}]};
  writeFileSync(path,JSON.stringify(state));
  let writes=0,failSave=false,nextId=1;
  const commit=fn=>{
    const before=structuredClone(state);
    try{
      fn();
      if(failSave)throw new Error('C:/private/test-user/quota');
      writeFileSync(path+'.tmp',JSON.stringify(state));renameSync(path+'.tmp',path);writes++;return true;
    }catch{state=before;return false;}
  };
  const controller=()=>createWorkDraftController({getState:()=>state,commit,makeId:()=>`work-${nextId++}`,now:()=>clock});
  return {controller,state:()=>state,path,writes:()=>writes,fail:()=>{failSave=true;},reopen:()=>{state=JSON.parse(readFileSync(path,'utf8'));}};
}

test('missing materials can be saved and reopened from durable JSON without starting a run',t=>{
  const h=host(t),before=structuredClone(h.state().runs);
  const work=h.controller().save({contextId:'project',draft:draft()});
  assert.equal(work.revision,1);assert.equal(work.status,'draft');assert.equal(work.completeness,'needs_input');
  assert.deepEqual(work.missing,['materials']);assert.deepEqual(h.state().runs,before);
  h.reopen();
  assert.deepEqual(h.controller().get({contextId:'project',workId:work.workId}),work);
  assert.equal(h.writes(),1);
});

test('matching revision updates once; stale editor cannot overwrite newer persisted requirements',t=>{
  const h=host(t),controller=h.controller();
  const first=controller.save({contextId:'project',draft:draft()});
  const second=controller.save({contextId:'project',workId:first.workId,expectedRevision:1,draft:draft({goal:'New requirement'})});
  assert.equal(second.revision,2);
  const before=readFileSync(h.path,'utf8');
  assert.throws(()=>controller.save({contextId:'project',workId:first.workId,expectedRevision:1,draft:draft({goal:'stale'})}),code('REVISION_CONFLICT'));
  assert.equal(readFileSync(h.path,'utf8'),before);assert.equal(h.writes(),2);
});

test('material links retain exact historical IDs and block unlinked materials or another project source',async t=>{
  const h=host(t),controller=h.controller(),docIds=['v1','v1'];
  const work=controller.save({contextId:'project',draft:draft({docIds})});
  assert.equal(work.completeness,'specified');assert.deepEqual(work.materialRefs,[{versionId:'v1',status:'referenced',materialId:'lecture',versionNumber:1}]);
  h.reopen();
  const pinned=h.controller().get({contextId:'project',workId:work.workId}).materialRefs[0];
  const reader=createMaterialReader({getState:h.state,readOriginal:async id=>new Blob([id==='v1'?'old lecture':'new lecture'],{type:'text/plain'})});
  assert.equal((await reader.readArtifact({contextId:'project',artifactId:'text:'+pinned.versionId})).content,'old lecture');
  docIds.push('v2');work.materialRefs[0].versionId='consumer edit';
  assert.deepEqual(h.state().requests[0].docIds,['v1']);
  assert.throws(()=>controller.save({contextId:'other',draft:draft({docIds:['v1']})}),code('INVALID_REFERENCE'));
  assert.throws(()=>controller.save({contextId:'project',draft:draft({sourceIds:['portal']})}),code('INVALID_REFERENCE'));
  assert.equal(h.writes(),1);
});

test('storage failure returns no saved receipt and preserves last confirmed state and bytes',t=>{
  const h=host(t),controller=h.controller();
  const work=controller.save({contextId:'project',draft:draft()});
  const before=readFileSync(h.path,'utf8');h.fail();
  assert.throws(()=>controller.save({contextId:'project',workId:work.workId,expectedRevision:1,draft:draft({goal:'Unsaved change'})}),
    error=>error.code==='SAVE_FAILED'&&!error.message.includes('private'));
  assert.equal(readFileSync(h.path,'utf8'),before);
  h.reopen();assert.equal(controller.get({contextId:'project',workId:work.workId}).instruction,work.instruction);
});

test('removed material reference remains an explicit issue when reopening; saving cannot restore access',t=>{
  const h=host(t),controller=h.controller();
  const work=controller.save({contextId:'project',draft:draft({docIds:['v1']})});
  h.state().libraryRefs=[];
  const reopened=controller.get({contextId:'project',workId:work.workId});
  assert.deepEqual(reopened.missing,['material_reference']);assert.equal(reopened.materialRefs[0].materialId,null);
  assert.throws(()=>controller.save({contextId:'project',workId:work.workId,expectedRevision:1,draft:draft({docIds:['v1']})}),code('INVALID_REFERENCE'));
  const fixed=controller.save({contextId:'project',workId:work.workId,expectedRevision:1,draft:draft()});
  assert.deepEqual(fixed.missing,['materials']);
});

test('legacy revision zero is explicit; editing preserves creation time and old run snapshot',t=>{
  const h=host(t),controller=h.controller();
  h.state().requests.push({id:'legacy',projectId:'project',...draft(),status:'ready',created:'2026-10-01T00:00:00.000Z'});
  const before=structuredClone(h.state().runs);
  assert.equal(controller.get({contextId:'project',workId:'legacy'}).revision,0);
  assert.throws(()=>controller.save({contextId:'project',workId:'legacy',draft:draft()}),code('REVISION_CONFLICT'));
  const work=controller.save({contextId:'project',workId:'legacy',expectedRevision:0,draft:draft({goal:'Revised'})});
  assert.equal(work.revision,1);assert.equal(h.state().requests[0].created,'2026-10-01T00:00:00.000Z');
  assert.deepEqual(h.state().runs,before);
});

test('foreign work and duplicate generated IDs cannot modify saved records',t=>{
  const h=host(t),controller=h.controller(),work=controller.save({contextId:'project',draft:draft()});
  assert.throws(()=>controller.get({contextId:'other',workId:work.workId}),code('UNAVAILABLE'));
  assert.throws(()=>controller.save({contextId:'other',workId:work.workId,expectedRevision:1,draft:draft()}),code('UNAVAILABLE'));
  const collision=createWorkDraftController({getState:h.state,commit:fn=>{fn();return true;},makeId:()=>work.workId,now:()=>clock});
  assert.throws(()=>collision.save({contextId:'project',draft:draft()}),code('INVALID_ID'));
  assert.equal(h.state().requests.length,1);assert.equal(h.writes(),1);
});

test('oversized or malformed requirements reject without truncation or persistence',t=>{
  const h=host(t),controller=h.controller();
  for(const change of [{goal:'x'.repeat(12001)},{deliverable:'x'.repeat(2001)},{title:'x'.repeat(101)},
    {goal:' '},{mode:'arbitrary-script'},{docIds:'v1'},{docIds:['../v1']},{docIds:Array(101).fill('v1')}]){
    assert.throws(()=>controller.save({contextId:'project',draft:draft(change)}),code('INVALID_DRAFT'));
  }
  assert.equal(h.writes(),0);assert.equal(h.state().requests.length,0);
});
