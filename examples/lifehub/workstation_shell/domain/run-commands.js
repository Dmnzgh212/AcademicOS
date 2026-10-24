import {getWorkDraft} from './work-drafts.js';
import {visibleDoc} from '../ui/document-scope.js';

// Request admission only. No executor, timers, network, browser or model calls.
export const RUN_LIMITS=Object.freeze({commands:1000,runs:1000,inputs:100,resources:20,textChars:120000,eventPage:100});
export class RunCommandError extends Error {
  constructor(code,message){super(message);this.name='RunCommandError';this.code=code;}
}
const fail=(code,message)=>{throw new RunCommandError(code,message);};
const validId=id=>typeof id==='string'&&id.length>0&&id.length<=160&&!/[\s/\\\u0000]/.test(id);
const own=(value,key)=>Object.prototype.hasOwnProperty.call(value,key);
function scope(state,contextId){
  if(!validId(contextId))fail('INVALID_ID','课程或项目标识无效。');
  if(!state||!Array.isArray(state.projects)||!Array.isArray(state.runs)||
     (state.runCommands!=null&&!Array.isArray(state.runCommands)))fail('INVALID_STATE','运行记录不可用。');
  if(!state.projects.some(project=>project?.id===contextId))fail('UNAVAILABLE','课程或项目不可用。');
}
function commandPayload(command){
  const {contextId,commandId,workId,expectedRevision,inputVersionIds,resourceRefs=[]}=command;
  if(!validId(commandId)||!validId(workId)||!Number.isSafeInteger(expectedRevision)||expectedRevision<1)
    fail('INVALID_COMMAND','需要命令标识、工作标识和已保存的工作版本。');
  if(!Array.isArray(inputVersionIds)||inputVersionIds.length>RUN_LIMITS.inputs||inputVersionIds.some(id=>!validId(id))||
     new Set(inputVersionIds).size!==inputVersionIds.length)fail('INVALID_COMMAND','材料版本列表无效。');
  if(!Array.isArray(resourceRefs)||resourceRefs.length>RUN_LIMITS.resources||resourceRefs.some(ref=>
    !ref||!validId(ref.resourceId)||!validId(ref.version))||new Set(resourceRefs.map(ref=>ref.resourceId)).size!==resourceRefs.length)
    fail('INVALID_COMMAND','资源版本列表无效。');
  const payload={workId,expectedRevision,inputVersionIds:[...inputVersionIds],resourceRefs:resourceRefs.map(({resourceId,version})=>({resourceId,version}))};
  return {contextId,commandId,payload,key:JSON.stringify(payload)};
}
function ownedRun(state,contextId,runId){
  if(!validId(runId))fail('INVALID_ID','运行标识无效。');
  const matches=state.runs.filter(run=>run?.id===runId);
  if(matches.length>1)fail('INVALID_STATE','运行标识重复。');
  const run=matches[0];
  if(!run||run.projectId!==contextId)fail('UNAVAILABLE','当前项目无法读取这次运行。');
  if(run.runSchemaVersion!==1)fail('UNSUPPORTED_RUN','此运行使用旧格式，请从原运行记录查看。');
  return run;
}
function replay(state,parsed){
  const matches=(state.runCommands||[]).filter(item=>item?.contextId===parsed.contextId&&item.commandId===parsed.commandId);
  if(matches.length>1)fail('INVALID_STATE','命令记录重复。');
  if(!matches.length)return null;
  const saved=matches[0];
  if(saved.kind!=='local-organize@1'||saved.payloadKey!==parsed.key)fail('COMMAND_CONFLICT','同一命令标识已用于另一份请求，请重新建立命令。');
  const run=ownedRun(state,parsed.contextId,saved.runId);
  if(run.commandId!==parsed.commandId||run.requestId!==parsed.payload.workId||run.workRevision!==parsed.payload.expectedRevision||
     typeof saved.acceptedAt!=='string'||!Number.isFinite(Date.parse(saved.acceptedAt))||run.created!==saved.acceptedAt||
     JSON.stringify(run.inputVersionIds)!==JSON.stringify(parsed.payload.inputVersionIds)||
     JSON.stringify(run.resourceRefs)!==JSON.stringify(parsed.payload.resourceRefs))fail('INVALID_STATE','命令与运行记录不一致。');
  return {status:'accepted',commandId:parsed.commandId,runId:run.id,acceptedAt:saved.acceptedAt,replayed:true};
}
export function findRunCommand(state,command){
  scope(state,command.contextId);
  return replay(state,commandPayload(command));
}
function resources(state,contextId,refs){
  const selected=state.projectResources&&own(state.projectResources,contextId)?state.projectResources[contextId]:[];
  if(!Array.isArray(selected)||selected.length>RUN_LIMITS.resources||selected.some(ref=>!ref||!validId(ref.resourceId)||!validId(ref.version))||
     new Set(selected.map(ref=>ref.resourceId)).size!==selected.length)fail('INVALID_STATE','项目资源选择记录无效。');
  if(selected.length!==refs.length||refs.some((ref,i)=>ref.resourceId!==selected[i].resourceId||ref.version!==selected[i].version))
    fail('RESOURCE_CONFLICT','项目资源选择已改变，请重新确认版本。');
  let chars=0;
  if(refs.length&&!Array.isArray(state.resourceCatalog))fail('INVALID_STATE','资源目录不可用。');
  return refs.map(ref=>{
    const matches=(state.resourceCatalog||[]).filter(resource=>resource?.id===ref.resourceId);
    if(matches.length!==1)fail('INVALID_RESOURCE','所选资源不存在或标识重复。');
    const resource=matches[0],versions=Array.isArray(resource.versions)?resource.versions.filter(version=>version?.version===ref.version):null;
    if(!Array.isArray(versions)||versions.length!==1||typeof resource.name!=='string'||resource.name.length>160||
       !['skill','method','script'].includes(resource.kind)||typeof versions[0].body!=='string'||versions[0].body.length>12000)
      fail('INVALID_RESOURCE','所选资源版本不可用。');
    chars+=versions[0].body.length;
    if(chars>RUN_LIMITS.textChars)fail('TOO_LARGE','资源快照过大，请减少选择。');
    return {id:resource.id,name:resource.name,kind:resource.kind,version:ref.version,body:versions[0].body};
  });
}

export function acceptRunCommand(state,command,{makeId=()=>crypto.randomUUID(),now=()=>new Date().toISOString()}={}){
  scope(state,command.contextId);
  const parsed=commandPayload(command),existing=replay(state,parsed);
  if(existing)return {state,receipt:existing};
  if((state.runCommands||[]).length>=RUN_LIMITS.commands||state.runs.length>=RUN_LIMITS.runs)
    fail('CAPACITY','运行或命令记录已达本阶段上限，请先归档；不会自动丢弃去重记录。');
  const {contextId,commandId,payload}=parsed,work=getWorkDraft(state,{contextId,workId:payload.workId});
  if(work.revision!==payload.expectedRevision)fail('REVISION_CONFLICT','工作要求已改变，请重新打开后运行。');
  if(work.mode!=='organize'||work.sourceIds.length)fail('UNSUPPORTED_WORK','本阶段只受理不含网站来源的本地材料整理。');
  if(work.completeness!=='specified')fail('INPUT_REQUIRED','请先补齐可引用的本地材料。');
  if(JSON.stringify(work.materialRefs.map(ref=>ref.versionId))!==JSON.stringify(payload.inputVersionIds))
    fail('INPUT_CONFLICT','材料版本选择已改变，请重新确认。');
  const selectedResources=resources(state,contextId,payload.resourceRefs);
  const docs=payload.inputVersionIds.map(id=>{
    const doc=state.docs.find(item=>item.id===id);
    if(typeof doc.name!=='string'||!doc.name||doc.name.length>512||(doc.type!=null&&(typeof doc.type!=='string'||doc.type.length>128)))
      fail('INVALID_STATE','材料快照记录无效。');
    return {id:doc.id,projectId:doc.projectId,materialId:doc.materialId||doc.id,version:doc.version??1,name:doc.name,
      type:doc.type||'',size:Number.isFinite(doc.size)&&doc.size>=0?doc.size:null,
      sha:typeof doc.sha==='string'&&/^[a-f\d]{64}$/i.test(doc.sha)?doc.sha:''};
  });
  let chars=0;
  const manualTexts=Object.fromEntries(payload.inputVersionIds.flatMap(id=>{
    if(!state.documentTexts||!own(state.documentTexts,id)||state.documentTexts[id]==null)return [];
    const text=state.documentTexts[id];
    if(typeof text!=='string')fail('INVALID_STATE','材料正文快照无效。');
    chars+=text.length;if(chars>RUN_LIMITS.textChars)fail('TOO_LARGE','材料正文快照过大，请拆分工作。');
    return [[id,text]];
  }));
  const timestamp=now(),runId=makeId('run'),eventId=makeId('event');
  if(typeof timestamp!=='string'||!Number.isFinite(Date.parse(timestamp))||!validId(runId)||!validId(eventId)||runId===eventId||
     state.runs.some(run=>run?.id===runId)||state.runs.some(run=>run?.events?.some(event=>event.eventId===eventId)))
    fail('INVALID_STATE','无法建立唯一运行记录。');
  const saved=state.requests.find(request=>request.id===work.workId);
  const request={id:saved.id,projectId:contextId,title:work.title,goal:work.instruction,deliverable:work.expectedOutput,
    mode:'organize',docIds:[...payload.inputVersionIds],sourceIds:[],revision:work.revision,created:saved.created};
  const message='运行请求已保存，等待本地执行器。';
  const run={id:runId,runSchemaVersion:1,commandId,requestId:work.workId,workRevision:work.revision,projectId:contextId,
    title:work.title,mode:'organize',request,docs,sources:[],manualTexts,resources:selectedResources,
    inputVersionIds:[...payload.inputVersionIds],resourceRefs:structuredClone(payload.resourceRefs),
    tasks:[],prefs:null,steps:[['scope','确认工作范围'],['read','读取材料正文'],['prepare','生成资料索引'],['save','保存目录']]
      .map(([key,label])=>({key,label,status:'pending'})),cursor:0,status:'queued',materials:[],artifactIds:[],created:timestamp,message,
    events:[{eventId,runId,seq:1,kind:'accepted',stepId:null,time:timestamp,message}]};
  const record={contextId,commandId,kind:'local-organize@1',payloadKey:parsed.key,runId,acceptedAt:timestamp};
  return {state:{...state,runs:[run,...state.runs],runCommands:[record,...(state.runCommands||[])]},
    receipt:{status:'accepted',commandId,runId,acceptedAt:timestamp,replayed:false}};
}

export function readRun(state,{contextId,runId,afterSeq=0,limit=50}){
  scope(state,contextId);
  if(!Number.isSafeInteger(afterSeq)||afterSeq<0||!Number.isSafeInteger(limit)||limit<1||limit>RUN_LIMITS.eventPage)
    fail('INVALID_CURSOR','运行记录游标或分页大小无效。');
  const run=ownedRun(state,contextId,runId);
  if(!Array.isArray(run.inputVersionIds)||run.inputVersionIds.length>RUN_LIMITS.inputs||run.inputVersionIds.some(id=>!validId(id))||
     !Array.isArray(run.resourceRefs)||run.resourceRefs.length>RUN_LIMITS.resources||run.resourceRefs.some(ref=>!ref||!validId(ref.resourceId)||!validId(ref.version))||!Array.isArray(run.steps)||
     run.steps.some(step=>!step||typeof step.key!=='string'||typeof step.label!=='string'||typeof step.status!=='string'))
    fail('INVALID_STATE','运行快照记录无效。');
  if(!Array.isArray(run.events)||!run.events.length||run.events.length>1000||run.events.some((event,i)=>
    !event||event.seq!==i+1||event.runId!==runId||!validId(event.eventId)||typeof event.kind!=='string'||event.kind.length>60||
    typeof event.message!=='string'||event.message.length>1000))fail('INVALID_STATE','运行事件顺序或内容无效。');
  if(new Set(run.events.map(event=>event.eventId)).size!==run.events.length)fail('INVALID_STATE','运行事件标识重复。');
  const lastSeq=run.events.at(-1).seq;
  if(afterSeq>lastSeq)fail('INVALID_CURSOR','游标超过已有记录，请重新打开运行。');
  if(!Array.isArray(state.docs)||!Array.isArray(state.libraryRefs)||state.libraryRefs.some(ref=>!ref))
    fail('INVALID_STATE','材料引用记录不可用。');
  const inputScopeAvailable=run.inputVersionIds.every(id=>{
    const matches=state.docs.filter(doc=>doc?.id===id);
    return matches.length===1&&visibleDoc(state,matches[0],contextId);
  });
  const events=run.events.filter(event=>event.seq>afterSeq).slice(0,limit).map(event=>({
    eventId:event.eventId,runId,seq:event.seq,kind:event.kind,stepId:event.stepId,time:event.time,message:event.message}));
  return {api:'lifehub.workstation.run@1',runId,workId:run.requestId,workRevision:run.workRevision,commandId:run.commandId,
    contextId,title:run.title,status:run.status,created:run.created,inputVersionIds:[...run.inputVersionIds],
    resourceRefs:run.resourceRefs.map(({resourceId,version})=>({resourceId,version})),inputScopeAvailable,steps:run.steps.map(({key,label,status})=>({key,label,status})),
    events,lastSeq,nextSeq:events.at(-1)?.seq??afterSeq};
}
