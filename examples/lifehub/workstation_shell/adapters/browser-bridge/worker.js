import {readBoundPage,pageCanRefresh} from './page-reader.js';
const SITE='https://lifehub-workstation.zhihangz212.chatgpt.site';
const locks=new Map(),controlLocks=new Set();let storageQueue=Promise.resolve(),inboxQueue=Promise.resolve();
const get=async()=> (await chrome.storage.session.get('targets')).targets||{};
const put=targets=>chrome.storage.session.set({targets});
const url=v=>{const u=new URL(v);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw Error('不支持的页面地址。');u.hash='';return u.href;};
const event=(t,message)=>{t.events||=[];t.events.push({time:new Date().toISOString(),message});t.events=t.events.slice(-100);};
function mutate(fn){const op=storageQueue.then(async()=>{const targets=await get(),result=await fn(targets);await put(targets);return result;});storageQueue=op.catch(()=>{});return op;}
async function update(id,fn){return mutate(targets=>{const t=targets[id];if(!t)throw Error('目标已失效，请重新绑定。');fn(t);return t;});}
async function target(id){const targets=await get(),t=targets[id];if(!t)throw Error('目标已失效，请重新绑定。');const tab=await chrome.tabs.get(t.tabId);if(url(tab.url)!==t.url)throw Error('绑定页面已跳转，暂停自动动作；请接管或重新绑定。');return t;}
async function inject(t,fn,args=[]){const results=await chrome.scripting.executeScript({target:{tabId:t.tabId,frameIds:[0]},func:fn,args});if(results.length!==1||results[0].error||!results[0].result)throw Error(results[0]?.error?.message||'页面读取器没有返回有效结果。');return results[0].result;}
function changeInbox(fn){const op=inboxQueue.then(async()=>{const {inbox=[]}=await chrome.storage.local.get('inbox');await chrome.storage.local.set({inbox:fn(inbox)});});inboxQueue=op.catch(()=>{});return op;}
async function archiveInbox(item){await changeInbox(inbox=>{const old=inbox.find(x=>x.targetId===item.targetId);if(old?.capture&&item.capture&&old.capture.sha!==item.capture.sha)throw Error('上次变化尚未归档，保留待归档版本。');return [...inbox.filter(x=>x.targetId!==item.targetId),item];});}
async function collect(id,refresh=false){
 if(locks.has(id)||controlLocks.has(id))throw Error('该页面正在处理或交接，请稍后。');
 const op=(async()=>{let t=await target(id);if(t.owner!=='system'||t.stopped)throw Error('自动读取已暂停。');if(!t.sourceId||!t.selector)throw Error('来源范围尚未配置。');
  await update(id,x=>{x.status='running';event(x,refresh?'轮询：刷新绑定页面':'开始读取指定范围');});
  try{
   if(refresh){await inject(t,pageCanRefresh);if((await target(id)).owner!=='system')throw Error('已请求暂停。');await chrome.tabs.reload(t.tabId);const deadline=Date.now()+20000;while((await chrome.tabs.get(t.tabId)).status!=='complete'){if(Date.now()>deadline)throw Error('页面刷新超时。');await new Promise(r=>setTimeout(r,300));}await new Promise(r=>setTimeout(r,1000));}
   t=await target(id);if(t.owner!=='system')throw Error('已请求暂停。');const capture=await inject(t,readBoundPage,[t.selector,t.url]);
   if(url(capture.url)!==t.url)throw Error('读取时发生跳转，未提交快照。');
   const bytes=new TextEncoder().encode(capture.text+'\n'+JSON.stringify(capture.links));capture.sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
   capture.originalSha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(capture.html)))].map(n=>n.toString(16).padStart(2,'0')).join('');
   const previous=(await chrome.storage.local.get('inbox')).inbox?.find(x=>x.targetId===id&&x.capture);if(previous&&previous.capture.sha!==capture.sha)throw Error('上次变化尚未归档。先打开工作站完成归档，再继续检查。');
   await archiveInbox({targetId:id,sourceId:t.sourceId,capture,time:capture.capturedAt});await update(id,x=>{x.status=x.owner==='system'?'ready':'paused';x.lastRead=capture.capturedAt;event(x,'读取完成，等待归档确认：'+capture.text.length+' 字符');});return capture;
  }catch(e){await update(id,x=>{x.status=x.owner==='system'?'failed':'paused';event(x,'读取失败：'+e.message);});throw e;}
 })();locks.set(id,op);try{return await op;}finally{locks.delete(id);}
}
async function control(id,command){
 if(controlLocks.has(id))throw Error('控制权正在交接。');controlLocks.add(id);
 try{
  if(!['pause','stop','takeover','resume'].includes(command))throw Error('无效控制动作。');
  if(command==='resume'){if(locks.has(id))throw Error('当前动作尚未结束。');const t=await target(id);await inject(t,pageCanRefresh);await update(id,x=>{x.owner='system';x.stopped=false;x.status='ready';event(x,'重新核对绑定页面后，交回自动读取');});return;}
  await update(id,x=>{x.owner=command==='takeover'?'user':'paused';x.status='pausing';if(command==='stop')x.stopped=true;event(x,'收到 '+command+'，禁止后续动作');});
  const t=(await get())[id];if(t.chatRunId){await chrome.tabs.sendMessage(t.tabId,{type:'cancel',id:t.chatRunId}).catch(()=>{});await update(id,x=>{x.chatActive=false;x.chatError='已停止等待，已经发送的消息不会撤销。请查看原聊天或导入回复。';});}
  if(locks.has(id))await locks.get(id).catch(()=>{});
  await update(id,x=>{x.status=command==='stop'?'stopped':'paused';event(x,'当前动作已结束，'+(command==='takeover'?'用户接管':'已确认 '+command));});
  if(command==='takeover'){await chrome.tabs.update(t.tabId,{active:true});const tab=await chrome.tabs.get(t.tabId);await chrome.windows.update(tab.windowId,{focused:true});}
 }finally{controlLocks.delete(id);}
}
async function handle(message,sender){
 if(message.type==='popup'){
  if(sender.tab||sender.id!==chrome.runtime.id)throw Error('无效弹窗来源。');
  if(message.action==='bind'){const [tab]=await chrome.tabs.query({active:true,currentWindow:true});if(!tab?.id||url(tab.url).startsWith(SITE))throw Error('先切到要读取的来源页面。');const existing=Object.values(await get()).find(t=>t.tabId===tab.id);if(existing&&(locks.has(existing.id)||existing.chatActive||controlLocks.has(existing.id)))throw Error('先停止当前动作再重新绑定。');if(existing?.monitor)await chrome.debugger.detach({tabId:tab.id}).catch(()=>{});const id=existing?.id||crypto.randomUUID();await mutate(targets=>{targets[id]={...existing,id,tabId:tab.id,url:url(tab.url),title:tab.title,owner:'system',stopped:false,monitor:false,status:'ready',controllerTabId:null,events:existing?.events||[]};event(targets[id],'用户绑定当前页面');});return {ok:true,id};}
  if(message.action==='monitor'){const [tab]=await chrome.tabs.query({active:true,currentWindow:true}),t=Object.values(await get()).find(t=>t.tabId===tab?.id);if(!t)throw Error('先绑定当前页面。');await target(t.id);if(!t.monitor)await chrome.debugger.attach({tabId:t.tabId},'1.3');await update(t.id,x=>{x.monitor=true;event(x,'监控绑定页面已启用');});return {ok:true};}
  if(message.action==='status')return {ok:true,targets:Object.values(await get()).map(t=>({id:t.id,title:t.title,url:t.url,monitor:t.monitor}))};
  if(message.action==='disconnect'){const targets=await get();for(const t of Object.values(targets)){await control(t.id,'stop');if(t.monitor)await chrome.debugger.detach({tabId:t.tabId}).catch(()=>{});await chrome.alarms.clear('lifehub:'+t.id);}await mutate(targets=>{for(const id of Object.keys(targets))delete targets[id];});return {ok:true};}
 }
 if(message.type==='progress'||message.type==='error'||message.type==='done'||message.type==='draft'){
  const t=Object.values(await get()).find(t=>t.tabId===sender.tab?.id&&t.chatRunId===message.id);if(!t||!t.chatActive)return {ok:false};
  await update(t.id,x=>{if(message.type==='progress'){x.status='chat-waiting';event(x,message.status);}else if(message.type==='done'){x.chatAnswer=message.answer;x.chatActive=false;x.status='ready';event(x,'完整回复已取得，等待工作站保存');}else{x.chatActive=false;x.chatError=message.error||'已有草稿，未覆盖。';x.status='waiting';event(x,x.chatError);}});return {ok:true};
 }
 if(message.type!=='station'||!sender.tab?.id||new URL(sender.url||sender.tab.url).origin!==SITE)throw Error('未授权的工作站来源。');
 const a=message.action,p=message.payload||{};
 if(['configure','poll','collect','control','focus','frame','chat-start'].includes(a))await update(p.targetId,t=>{if(t.controllerTabId&&t.controllerTabId!==sender.tab.id)throw Error('另一工作站标签页持有控制权。请在原工作站操作，或用扩展重新绑定。');t.controllerTabId=sender.tab.id;});
 if(a==='status')return {ok:true,targets:Object.values(await get()).map(t=>({id:t.id,title:t.title,url:t.url,owner:t.owner,status:t.status,monitor:!!t.monitor})),heartbeat:new Date().toISOString()};
 if(a==='inbox')return {ok:true,items:(await chrome.storage.local.get('inbox')).inbox||[]};
 if(a==='ack'){await changeInbox(inbox=>inbox.filter(x=>!(x.targetId===p.targetId&&x.time===p.capturedAt)));return {ok:true};}
 if(a==='configure'||a==='poll'){
  const t=await target(p.targetId);if(t.owner!=='system'||locks.has(t.id)||controlLocks.has(t.id)||t.chatActive)throw Error('先交回控制权并等待当前动作结束。');if(url(p.url)!==t.url||typeof p.sourceId!=='string'||!p.sourceId||typeof p.selector!=='string'||!p.selector||p.selector.length>200)throw Error('来源地址或范围无效。');
  await update(t.id,x=>{x.sourceId=p.sourceId;x.selector=p.selector;event(x,'配置读取范围：'+p.selector);});
  if(a==='poll'){if(![0,5,15,30,60].includes(p.minutes))throw Error('无效轮询间隔。');await chrome.alarms.clear('lifehub:'+t.id);await update(t.id,x=>x.pollMinutes=p.minutes);if(p.minutes)await chrome.alarms.create('lifehub:'+t.id,{periodInMinutes:p.minutes});}return {ok:true};
 }
 if(a==='collect'){const t=await target(p.targetId);if(t.sourceId!==p.sourceId||t.url!==url(p.url)||t.selector!==p.selector||t.chatActive)throw Error('来源或范围与本地绑定不一致，或聊天正在运行。');return {ok:true,capture:await collect(t.id)};}
 if(a==='control'){await control(p.targetId,p.command);return {ok:true};}
 if(a==='focus'){const t=await target(p.targetId);await chrome.tabs.update(t.tabId,{active:true});const tab=await chrome.tabs.get(t.tabId);await chrome.windows.update(tab.windowId,{focused:true});return {ok:true};}
 if(a==='frame'){const t=await target(p.targetId);if(!t.monitor)throw Error('在绑定标签页的扩展弹窗启用监控。');const frame=await chrome.debugger.sendCommand({tabId:t.tabId},'Page.captureScreenshot',{format:'jpeg',quality:60,captureBeyondViewport:false});const current=await target(p.targetId);if(!current.monitor)throw Error('画面连接已经断开。');return {ok:true,image:frame.data,capturedAt:new Date().toISOString(),target:{id:current.id,url:current.url,owner:current.owner,status:current.status},events:current.events};}
 if(a==='chat-start'){
  if(locks.has(p.targetId)||controlLocks.has(p.targetId))throw Error('目标正在处理，请勿重复发送。');
  const op=(async()=>{const t=await target(p.targetId);if(new URL(t.url).hostname!=='chatgpt.com'||!new URL(t.url).pathname.includes('/c/')||t.owner!=='system'||t.stopped||t.chatActive)throw Error('聊天目标未就绪，请绑定已有会话页面。');if(typeof p.prompt!=='string'||p.prompt.length>30000||!p.prompt.trim()||typeof p.runId!=='string')throw Error('提问最多30,000字符。');
  const seen=(await chrome.storage.local.get('chatSeen')).chatSeen||[];if(seen.includes(p.runId))throw Error('这次运行已经尝试发送。请检查原聊天，不会重复发送。');
  await chrome.storage.local.set({chatSeen:[...seen,p.runId].slice(-1000)});const id=crypto.randomUUID().replaceAll('-','');await update(t.id,x=>{x.chatRunId=id;x.workRunId=p.runId;x.chatActive=true;delete x.chatAnswer;delete x.chatError;x.status='chat-starting';event(x,'准备发送一次提问，已有草稿会阻止发送');});
  try{if((await target(t.id)).owner!=='system')throw Error('发送前收到暂停。');await chrome.scripting.executeScript({target:{tabId:t.tabId,frameIds:[0]},files:['chat.js']});if((await target(t.id)).owner!=='system')throw Error('发送前收到暂停。');const r=await chrome.tabs.sendMessage(t.tabId,{type:'run',run:{id,question:p.prompt,material:'',backupDraft:false}});if(!r.ok)throw Error(r.error);return {ok:true};}catch(e){await update(t.id,x=>{x.chatActive=false;x.chatError=e.message;x.status=x.owner==='system'?'waiting':'paused';});throw e;}
  })();locks.set(p.targetId,op);try{return await op;}finally{locks.delete(p.targetId);}
 }
 if(a==='chat-result'){const t=(await get())[p.targetId];if(!t||t.workRunId!==p.runId)throw Error('聊天运行不匹配。');return {ok:true,active:!!t.chatActive,answer:t.chatAnswer||'',error:t.chatError||''};}
 throw Error('不支持的动作。');
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{handle(message,sender).then(reply,e=>reply({ok:false,error:e.message}));return true;});
chrome.alarms.onAlarm.addListener(async alarm=>{if(!alarm.name.startsWith('lifehub:'))return;const id=alarm.name.slice(8),t=(await get())[id];if(!t){await chrome.alarms.clear(alarm.name);return;}if(t.owner!=='system'||t.stopped||t.chatActive||locks.has(id)||controlLocks.has(id))return;try{await collect(id,true);}catch(e){const {inbox=[]}=await chrome.storage.local.get('inbox');if(!inbox.some(x=>x.targetId===id&&x.capture))await archiveInbox({targetId:id,sourceId:t.sourceId,error:e.message,time:new Date().toISOString()});}});
chrome.debugger.onDetach.addListener(async source=>{const t=Object.values(await get()).find(t=>t.tabId===source.tabId);if(t)await update(t.id,x=>{x.monitor=false;x.owner='paused';x.status='paused';event(x,'画面连接断开，自动读取暂停');});});
chrome.tabs.onRemoved.addListener(async tabId=>{await mutate(async targets=>{for(const [id,t] of Object.entries(targets))if(t.tabId===tabId){delete targets[id];await chrome.alarms.clear('lifehub:'+id);}});});
