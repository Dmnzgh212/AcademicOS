import test from 'node:test';
import assert from 'node:assert/strict';
import {createMaterialReader,MATERIAL_LIMITS} from '../adapters/material-reader.js';

function fixture(){
  const state={projects:[{id:'course'},{id:'project'},{id:'other'}],
    docs:[{id:'v1',projectId:'course',materialId:'lecture',version:1,name:'lecture.txt',type:'text/plain',supersededBy:'v2'},
      {id:'v2',projectId:'course',materialId:'lecture',version:2,previousId:'v1',name:'lecture.txt',type:'text/plain'}],
    libraryRefs:[{projectId:'project',materialId:'lecture'}],documentTexts:{}};
  const originals=new Map([['v1',new Blob(['old lecture'],{type:'text/plain'})],['v2',new Blob(['new lecture'],{type:'text/plain'})]]);
  let reads=0;
  const reader=createMaterialReader({getState:()=>state,readOriginal:async id=>{reads++;return originals.get(id);}});
  return {state,originals,reader,reads:()=>reads};
}
const code=expected=>error=>error.code===expected;

test('linked project reads the requested historical version without following latest or modifying host records',async()=>{
  const f=fixture(),before=structuredClone(f.state);
  const view=await f.reader.getMaterial({contextId:'project',versionId:'v1'});
  assert.equal(view.versionNumber,1);assert.equal(view.versionId,'v1');assert.equal(view.contextId,'course');
  assert.equal(view.original.bytes,11);assert.equal(view.integrity,'not_checked');
  assert.equal(view.text.status,'pending_read');
  const result=await f.reader.readArtifact({contextId:'project',artifactId:view.text.artifactId});
  assert.equal(result.content,'old lecture');
  view.original.status='missing';view.name='consumer edit';
  assert.deepEqual(f.state,before);
});

test('unreferenced projects and path-shaped IDs fail before original storage is called',async()=>{
  const f=fixture();
  await assert.rejects(f.reader.getMaterial({contextId:'other',versionId:'v1'}),code('UNAVAILABLE'));
  await assert.rejects(f.reader.readArtifact({contextId:'other',artifactId:'original:v1'}),code('UNAVAILABLE'));
  await assert.rejects(f.reader.readArtifact({contextId:'project',artifactId:'original:../v1'}),code('INVALID_ID'));
  assert.equal(f.reads(),0);
});

test('missing original stays missing despite ready metadata, while saved empty text remains readable',async()=>{
  const f=fixture();f.originals.delete('v1');f.state.docs[0].readingState='ready';f.state.docs[0].size=11;
  let view=await f.reader.getMaterial({contextId:'course',versionId:'v1'});
  assert.equal(view.original.status,'missing');assert.equal(view.text.status,'missing');
  await assert.rejects(f.reader.readArtifact({contextId:'course',artifactId:'original:v1'}),code('MISSING_ORIGINAL'));
  f.state.documentTexts.v1='';view=await f.reader.getMaterial({contextId:'course',versionId:'v1'});
  assert.equal(view.text.status,'available');
  assert.equal((await f.reader.readArtifact({contextId:'course',artifactId:'text:v1'})).content,'');
});

test('PDF original is returned as bytes without claiming extracted text',async()=>{
  const f=fixture();Object.assign(f.state.docs[0],{name:'lecture.pdf',type:'application/pdf'});
  const blob=new Blob(['%PDF-1.7\nfixture'],{type:'application/pdf'});f.originals.set('v1',blob);
  const view=await f.reader.getMaterial({contextId:'course',versionId:'v1'});
  assert.equal(view.original.status,'available');assert.equal(view.text.status,'not_extracted');
  assert.equal((await f.reader.readArtifact({contextId:'course',artifactId:'original:v1'})).content,blob);
  await assert.rejects(f.reader.readArtifact({contextId:'course',artifactId:'text:v1'}),code('NOT_EXTRACTED'));
});

test('actual byte and character limits reject the whole result rather than truncating it',async()=>{
  const f=fixture();f.state.docs[0].size=1;
  f.originals.set('v1',new Blob([new Uint8Array(MATERIAL_LIMITS.originalBytes+1)],{type:'text/plain'}));
  assert.equal((await f.reader.getMaterial({contextId:'course',versionId:'v1'})).original.status,'too_large');
  await assert.rejects(f.reader.readArtifact({contextId:'course',artifactId:'original:v1'}),code('TOO_LARGE'));
  f.state.documentTexts.v1='x'.repeat(MATERIAL_LIMITS.textChars+1);
  await assert.rejects(f.reader.readArtifact({contextId:'course',artifactId:'text:v1'}),code('TOO_LARGE'));
  delete f.state.documentTexts.v1;
  f.originals.set('v1',new Blob(['x'.repeat(MATERIAL_LIMITS.textChars+1)]));
  await assert.rejects(f.reader.readArtifact({contextId:'course',artifactId:'text:v1'}),code('TOO_LARGE'));
});

test('scope removal during async host IO withholds both metadata and original results',async()=>{
  for(const operation of ['metadata','original']){
    const f=fixture();let release;
    const reader=createMaterialReader({getState:()=>f.state,readOriginal:()=>new Promise(resolve=>{release=resolve;})});
    const pending=operation==='metadata'?reader.getMaterial({contextId:'project',versionId:'v1'}):
      reader.readArtifact({contextId:'project',artifactId:'original:v1'});
    f.state.libraryRefs=[];release(f.originals.get('v1'));
    await assert.rejects(pending,code('UNAVAILABLE'));
  }
});

test('changed fixed-version records during async IO do not yield mixed provenance',async()=>{
  const f=fixture();let release;
  const reader=createMaterialReader({getState:()=>f.state,readOriginal:()=>new Promise(resolve=>{release=resolve;})});
  const pending=reader.readArtifact({contextId:'course',artifactId:'text:v1'});
  f.state.documentTexts.v1='edited while reading';release(f.originals.get('v1'));
  await assert.rejects(pending,code('STALE_VERSION'));
});

test('invalid encoding and host errors produce bounded errors without filesystem details',async()=>{
  const f=fixture();f.originals.set('v1',new Blob([new Uint8Array([0xff,0xfe,0xff])]));
  await assert.rejects(f.reader.readArtifact({contextId:'course',artifactId:'text:v1'}),code('UNSUPPORTED_ENCODING'));
  const reader=createMaterialReader({getState:()=>f.state,readOriginal:async()=>{throw new Error('C:/private/account/file.pdf');}});
  await assert.rejects(reader.getMaterial({contextId:'course',versionId:'v1'}),error=>error.code==='READ_FAILED'&&!error.message.includes('private'));
});
