// Route/handler checks only; this does not render pixels or verify browser layout.
import test from 'node:test';
import assert from 'node:assert/strict';
const elements=new Map(),listeners=new Map();
function element(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',open:false,dataset:{},className:'',querySelector:()=>null,showModal(){this.open=true;},close(){this.open=false;},focus(){},setSelectionRange(){}});return elements.get(id);}
globalThis.document={getElementById:element,querySelectorAll:()=>[],addEventListener:(name,fn)=>listeners.set(name,fn)};
globalThis.window={addEventListener:(name,fn)=>listeners.set('window:'+name,fn)};
globalThis.location={hash:'#work'};globalThis.localStorage={setItem:()=>{throw Error('Fixture must not write personal records');}};globalThis.fetch=()=>{throw Error('Fixture must not access a service');};
await import('../ui/reference.js');
async function click(action,id){await listeners.get('click')({preventDefault(){},target:{closest:()=>({dataset:{action,id}})}});}
test('all PPT UI fixture routes render with shared components and never require a service or personal persistence',async()=>{
 for(const [id,marker] of [['work','source-pane'],['schedule','schedule-time-axis'],['library','library-folders'],['sources','source-pipeline'],['monitor','ppt-browser'],['takeover','控制权已交给你'],['resources','本次固定 v']]){await click('reference-screen',id);assert.ok(element('main').innerHTML.includes(marker),id);}
 await click('station-monitor-inspector','run');assert.ok(element('main').innerHTML.includes('当前动作'));await click('station-monitor-tab','history');assert.ok(element('main').innerHTML.includes('页面动作历史'));
 await click('reference-screen','work');assert.ok(element('main').innerHTML.includes('sample-report'));await click('station-resource-view','explain');assert.ok(element('main').innerHTML.includes('catalog-stage'));
 await click('station-open-request','lab-work');assert.ok(element('crumb').innerHTML.includes('Lab 3 preparation'));
});
