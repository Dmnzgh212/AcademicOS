import {visibleDoc} from '../ui/document-scope.js';

// Adapted from the existing Site workflow.newRequest shape. Saving never runs work.
const modes=new Set(['learn','organize','collect','plan']);
const validId=id=>typeof id==='string'&&id.length>0&&id.length<=160&&!/[\s/\\\u0000]/.test(id);
export class WorkDraftError extends Error {
  constructor(code,message){super(message);this.name='WorkDraftError';this.code=code;}
}
const fail=(code,message)=>{throw new WorkDraftError(code,message);};
const revision=request=>{
  const value=request?.revision??0;
  if(!Number.isSafeInteger(value)||value<0)fail('INVALID_STATE','工作版本记录无效。');
  return value;
};
function field(value,max,label,required=false){
  if(value==null)value='';
  if(typeof value!=='string'||value.length>max)fail('INVALID_DRAFT',`${label}格式或长度无效。`);
  value=value.trim();
  if(required&&!value)fail('INVALID_DRAFT',`请填写${label}。`);
  return value;
}
function ids(value){
  if(value==null)return [];
  if(!Array.isArray(value)||value.length>100||value.some(id=>!validId(id)))fail('INVALID_DRAFT','材料或来源引用无效，每类最多 100 项。');
  return [...new Set(value)];
}
function context(state,contextId){
  if(!validId(contextId))fail('INVALID_ID','课程或项目标识无效。');
  if(!state||!Array.isArray(state.projects)||!Array.isArray(state.requests)||!Array.isArray(state.docs)||
     !Array.isArray(state.sources)||!Array.isArray(state.libraryRefs))fail('INVALID_STATE','工作区记录不可用。');
  if(!state.projects.some(project=>project?.id===contextId))fail('UNAVAILABLE','课程或项目不可用。');
  if(state.libraryRefs.some(ref=>!ref||!validId(ref.projectId)||!validId(ref.materialId)))fail('INVALID_STATE','材料引用记录无效。');
}
function requestFor(state,contextId,workId){
  if(!validId(workId))fail('INVALID_ID','工作标识无效。');
  const matches=state.requests.filter(item=>item?.id===workId);
  if(matches.length>1)fail('INVALID_STATE','工作标识重复。');
  if(!matches[0]||matches[0].projectId!==contextId)fail('UNAVAILABLE','当前项目无法打开这项工作。');
  return matches[0];
}
function materialRefs(state,contextId,docIds){
  return docIds.map(versionId=>{
    const matches=state.docs.filter(doc=>doc?.id===versionId);
    if(matches.length>1)fail('INVALID_STATE','材料版本标识重复。');
    const doc=matches[0];
    if(!doc||!visibleDoc(state,doc,contextId))return {versionId,status:'unavailable',materialId:null,versionNumber:null};
    const materialId=doc.materialId||doc.id,versionNumber=doc.version??1;
    if(!validId(materialId)||!Number.isSafeInteger(versionNumber)||versionNumber<1)fail('INVALID_STATE','材料版本记录无效。');
    return {versionId,status:'referenced',materialId,versionNumber};
  });
}
function view(state,request){
  if(!modes.has(request.mode))fail('INVALID_STATE','工作处理方式无效。');
  if(typeof request.title!=='string'||request.title.length>100||typeof request.goal!=='string'||request.goal.length>12000||
     (request.deliverable!=null&&(typeof request.deliverable!=='string'||request.deliverable.length>2000)))
    fail('INVALID_STATE','保存的工作要求无效。');
  const docIds=ids(request.docIds),sourceIds=ids(request.sourceIds);
  const refs=materialRefs(state,request.projectId,docIds);
  const unavailableSources=sourceIds.filter(id=>!state.sources.some(source=>source?.id===id&&source.projectId===request.projectId));
  const missing=[];
  if(['learn','organize'].includes(request.mode)&&!docIds.length)missing.push('materials');
  if(request.mode==='collect'&&!sourceIds.length)missing.push('source');
  if(refs.some(ref=>ref.status==='unavailable'))missing.push('material_reference');
  if(unavailableSources.length)missing.push('source_reference');
  return {api:'lifehub.workstation.work-draft@1',workId:request.id,contextId:request.projectId,
    title:request.title,instruction:request.goal,expectedOutput:request.deliverable||'',mode:request.mode,
    revision:revision(request),status:request.status||'draft',materialRefs:refs,sourceIds,
    unavailableSourceIds:unavailableSources,completeness:missing.length?'needs_input':'specified',missing};
}

export function getWorkDraft(state,{contextId,workId}){
  context(state,contextId);
  return view(state,requestFor(state,contextId,workId));
}

export function saveWorkDraft(state,{contextId,workId,expectedRevision,draft},
  {makeId=()=>crypto.randomUUID(),now=()=>new Date().toISOString()}={}){
  context(state,contextId);
  if(!draft||typeof draft!=='object'||Array.isArray(draft))fail('INVALID_DRAFT','请提供工作要求。');
  const previous=workId==null?null:requestFor(state,contextId,workId);
  if(previous?expectedRevision!==revision(previous):expectedRevision!=null&&expectedRevision!==0)
    fail('REVISION_CONFLICT','这项工作已改变，请重新打开后保存。');
  if(previous&&revision(previous)>=Number.MAX_SAFE_INTEGER)fail('REVISION_CONFLICT','工作版本已达上限。');
  const goal=field(draft.goal,12000,'处理要求',true),deliverable=field(draft.deliverable,2000,'期望产物');
  const title=field(draft.title,100,'工作名称')||goal.split('\n')[0].slice(0,100);
  if(!modes.has(draft.mode))fail('INVALID_DRAFT','请选择已有的处理方式。');
  const docIds=ids(draft.docIds),sourceIds=ids(draft.sourceIds);
  if(materialRefs(state,contextId,docIds).some(ref=>ref.status==='unavailable')||
     sourceIds.some(id=>!state.sources.some(source=>source?.id===id&&source.projectId===contextId)))
    fail('INVALID_REFERENCE','选中的材料或来源当前不可用，请重新选择。');
  const id=previous?.id??makeId(),timestamp=now();
  if(!validId(id)||(!previous&&state.requests.some(request=>request?.id===id)))fail('INVALID_ID','无法建立唯一工作标识。');
  if(typeof timestamp!=='string'||!Number.isFinite(Date.parse(timestamp)))fail('INVALID_STATE','保存时间无效。');
  const request={...(previous?structuredClone(previous):{}),id,projectId:contextId,title,goal,deliverable,mode:draft.mode,
    docIds,sourceIds,status:'draft',revision:revision(previous)+1,created:previous?.created??timestamp,updated:timestamp};
  const next={...state,requests:previous?state.requests.map(item=>item.id===id?request:item):[request,...state.requests]};
  return {state:next,work:view(next,request)};
}
