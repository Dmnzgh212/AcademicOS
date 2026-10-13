import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const code=fs.readFileSync(new URL('../adapters/browser-bridge/worker.js',import.meta.url),'utf8').replace(/^import .*\n/,'');
function harness(){
 let listener,alarmListener,detachListener,removeListener,session={},local={},active=7,readingGate=null;
 const calls=[],tabs=new Map([[7,{id:7,url:'https://example.com/lecture',title:'Lecture',windowId:1,status:'complete'}],[9,{id:9,url:'https://other.example.com/private',windowId:2,status:'complete'}]]);
 const storage=obj=>({get:async key=>structuredClone({[key]:obj===1?session[key]:local[key]}),set:async values=>{if(obj===1)Object.assign(session,structuredClone(values));else Object.assign(local,structuredClone(values));}});
 const chrome={runtime:{id:'extension',onMessage:{addListener:f=>listener=f}},storage:{session:storage(1),local:storage(2)},tabs:{query:async()=>[tabs.get(active)],get:async id=>{if(!tabs.has(id))throw Error('Tab closed');return {...tabs.get(id)};},reload:async id=>calls.push(['reload',id]),update:async id=>{active=id;},sendMessage:async(id,message)=>{calls.push(['message',id,message]);return {ok:true};},onRemoved:{addListener:f=>removeListener=f}},windows:{update:async()=>{}},alarms:{clear:async()=>true,create:async()=>{},onAlarm:{addListener:f=>alarmListener=f}},debugger:{attach:async t=>calls.push(['attach',t.tabId]),detach:async()=>{},sendCommand:async(t,method)=>{calls.push(['frame',t.tabId,method]);return {data:'YWJj'};},onDetach:{addListener:f=>detachListener=f}},scripting:{executeScript:async options=>{calls.push(['script',options.target.tabId,options.func?.name||options.files]);if(options.files)return [{}];if(options.func.name==='pageCanRefresh')return [{result:{ready:true,url:tabs.get(options.target.tabId).url}}];if(readingGate)await readingGate;return [{result:{status:'complete',scope:'bound-page',url:'https://example.com/lecture',selector:'main',text:'Actual body',html:'<main>Actual body</main>',links:[],capturedAt:new Date().toISOString()}}];}}};
 const context=vm.createContext({chrome,crypto:webcrypto,URL,Date,TextEncoder,setTimeout,readBoundPage:function readBoundPage(){},pageCanRefresh:function pageCanRefresh(){},Map,Set});vm.runInContext(code,context);
 const sender={id:'extension',url:'https://lifehub-workstation.zhihangz212.chatgpt.site/',tab:{id:22,url:'https://lifehub-workstation.zhihangz212.chatgpt.site/'}};
 const call=(message,from=sender)=>new Promise(resolve=>listener(message,from,resolve));
 const station=(action,payload={})=>call({type:'station',action,payload});
 const popup=action=>call({type:'popup',action},{id:'extension'});
 return {call,station,popup,calls,tabs,get session(){return session;},get local(){return local;},setActive:id=>active=id,gate:p=>readingGate=p,alarm:()=>alarmListener,detach:()=>detachListener,remove:()=>removeListener};
}
async function bound(h){const r=await h.popup('bind');assert.equal(r.ok,true);const id=r.id;assert.equal((await h.station('configure',{targetId:id,sourceId:'source',url:'https://example.com/lecture',selector:'main'})).ok,true);return id;}
test('extension stores a real scoped capture until ack, reads only the bound tab, and refuses an unknown sender',async()=>{
 const h=harness(),id=await bound(h);h.setActive(9);const r=await h.station('collect',{targetId:id,sourceId:'source',url:'https://example.com/lecture',selector:'main'});assert.equal(r.ok,true);assert.equal(r.capture.text,'Actual body');assert.match(r.capture.sha,/^[a-f0-9]{64}$/);assert.equal(h.local.inbox.length,1);assert.ok(h.calls.some(c=>c[0]==='script'&&c[1]===7));assert.ok(!h.calls.some(c=>c[0]==='script'&&c[1]===9));
 const bad=await h.call({type:'station',action:'inbox'},{url:'https://evil.example.com',tab:{id:4}});assert.equal(bad.ok,false);assert.match(bad.error,/未授权/);
 await h.station('ack',{targetId:id,capturedAt:r.capture.capturedAt});assert.equal(h.local.inbox.length,0);
 const other=await h.call({type:'station',action:'collect',payload:{targetId:id,sourceId:'source',url:'https://example.com/lecture',selector:'main'}},{id:'extension',url:'https://lifehub-workstation.zhihangz212.chatgpt.site/',tab:{id:23,url:'https://lifehub-workstation.zhihangz212.chatgpt.site/'}});assert.equal(other.ok,false);assert.match(other.error,/持有控制权/);
});
test('preview is target-bound, stops on navigation or debugger detachment, and never stores frames',async()=>{
 const h=harness(),id=await bound(h);assert.equal((await h.popup('monitor')).ok,true);h.setActive(9);const frame=await h.station('frame',{targetId:id});assert.equal(frame.ok,true);assert.equal(h.calls.find(c=>c[0]==='frame')[1],7);assert.ok(!JSON.stringify(h.local).includes('YWJj'));assert.ok(!JSON.stringify(h.session).includes('YWJj'));
 h.tabs.get(7).url='https://example.com/another';assert.equal((await h.station('frame',{targetId:id})).ok,false);assert.equal(h.calls.filter(c=>c[0]==='frame').length,1);h.tabs.get(7).url='https://example.com/lecture';await h.detach()({tabId:7});assert.equal((await h.station('frame',{targetId:id})).ok,false);assert.equal(h.session.targets[id].owner,'paused');
});
test('open-browser focuses only the validated bound tab and does not hand over or resume automation',async()=>{
 const h=harness(),id=await bound(h);h.setActive(9);assert.equal((await h.station('focus',{targetId:id})).ok,true);assert.equal(h.session.targets[id].owner,'system');
 const binding=await h.popup('bind');assert.equal(binding.id,id);assert.equal((await h.station('focus',{targetId:'unknown'})).ok,false);
 h.tabs.get(7).url='https://example.com/other';assert.equal((await h.station('focus',{targetId:id})).ok,false);
});
test('pause blocks the next read immediately and confirms only after the in-flight action has ended',async()=>{
 const h=harness(),id=await bound(h);let release;h.gate(new Promise(resolve=>release=resolve));const collect=h.station('collect',{targetId:id,sourceId:'source',url:'https://example.com/lecture',selector:'main'});
 for(let n=0;n<50&&!h.calls.some(c=>c[0]==='script');n++)await new Promise(r=>setTimeout(r,1));let confirmed=false;const control=h.station('control',{targetId:id,command:'takeover'}).then(r=>{confirmed=true;return r;});
 await new Promise(r=>setTimeout(r,5));assert.equal(confirmed,false);assert.equal(h.session.targets[id].owner,'user');assert.equal((await h.station('collect',{targetId:id,sourceId:'source',url:'https://example.com/lecture',selector:'main'})).ok,false);release();await collect;assert.equal((await control).ok,true);assert.equal(h.session.targets[id].status,'paused');assert.equal((await h.station('control',{targetId:id,command:'resume'})).ok,true);assert.equal(h.session.targets[id].owner,'system');
});
test('chat attempt is persisted once and cannot be repeated after worker requests sending',async()=>{
 const h=harness();h.tabs.get(7).url='https://chatgpt.com/c/test';const {id}=await h.popup('bind');const prompt={targetId:id,runId:'work-1',prompt:'Explain actual material'};assert.equal((await h.station('chat-start',prompt)).ok,true);assert.equal((await h.station('chat-start',prompt)).ok,false);
 const chatId=h.session.targets[id].chatRunId;await h.call({type:'done',id:chatId,answer:'Actual response'},{tab:{id:7}});const result=await h.station('chat-result',{targetId:id,runId:'work-1'});assert.equal(result.answer,'Actual response');const again=await h.station('chat-start',prompt);assert.equal(again.ok,false);assert.match(again.error,/已经尝试/);assert.equal(h.calls.filter(c=>c[0]==='message'&&c[2].type==='run').length,1);
});
