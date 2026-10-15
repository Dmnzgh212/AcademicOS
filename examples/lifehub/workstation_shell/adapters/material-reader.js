import {visibleDoc} from '../ui/document-scope.js';

// A read-only bridge over the existing browser host, not an authorization server.
export const MATERIAL_LIMITS = Object.freeze({originalBytes:2*1024*1024,textChars:120000});
export class MaterialReadError extends Error {
  constructor(code,message){super(message);this.name='MaterialReadError';this.code=code;}
}
const fail=(code,message)=>{throw new MaterialReadError(code,message);};
const validId=id=>typeof id==='string'&&id.length>0&&id.length<=160&&!/[\s/\\\u0000]/.test(id);
const own=(record,key)=>Object.prototype.hasOwnProperty.call(record,key);
const textFile=doc=>!(/\.pdf$/i.test(doc.name)||doc.type==='application/pdf')&&
  (doc.type?.startsWith('text/')||/\.(txt|md|csv|json|srt|vtt|java|py|js|ts|html|css|xml|ya?ml|log)$/i.test(doc.name));
const binding=doc=>JSON.stringify([doc.id,doc.projectId,doc.materialId||doc.id,doc.version||1,doc.sha||'',doc.name,doc.type||'']);

export function createMaterialReader({getState,readOriginal}) {
  if(typeof getState!=='function'||typeof readOriginal!=='function')throw new TypeError('需要宿主提供只读状态与原件读取函数。');

  function lookup(contextId,versionId){
    if(!validId(contextId)||!validId(versionId))fail('INVALID_ID','材料或项目标识无效。');
    const state=getState();
    if(!state||!Array.isArray(state.docs)||!Array.isArray(state.projects))fail('INVALID_STATE','材料状态不可用。');
    if(state.libraryRefs!=null&&(!Array.isArray(state.libraryRefs)||state.libraryRefs.some(ref=>
      !ref||typeof ref.projectId!=='string'||typeof ref.materialId!=='string')))fail('INVALID_STATE','材料引用记录无效。');
    const matches=state.docs.filter(doc=>doc?.id===versionId);
    if(matches.length>1)fail('INVALID_STATE','材料版本标识重复。');
    const doc=matches[0];
    if(!state.projects.some(project=>project?.id===contextId)||!doc||!visibleDoc(state,doc,contextId))
      fail('UNAVAILABLE','当前项目无法读取这份材料。');
    if(!validId(doc.projectId)||!validId(doc.materialId||doc.id)||
       !Number.isSafeInteger(doc.version??1)||(doc.version??1)<1||
       typeof doc.name!=='string'||!doc.name||doc.name.length>512||
       (doc.type!=null&&(typeof doc.type!=='string'||doc.type.length>128)))fail('INVALID_STATE','材料版本记录无效。');
    const text=state.documentTexts&&own(state.documentTexts,versionId)?state.documentTexts[versionId]:null;
    if(text!=null&&typeof text!=='string')fail('INVALID_STATE','保存的材料正文无效。');
    return {doc:{...doc},text:text??null};
  }

  function recheck(contextId,versionId,snapshot){
    const current=lookup(contextId,versionId);
    if(binding(current.doc)!==binding(snapshot.doc)||current.text!==snapshot.text)
      fail('STALE_VERSION','材料在读取期间发生变化，请重新打开该版本。');
  }

  async function load(contextId,versionId,snapshot){
    let blob;
    try{blob=await readOriginal(versionId);}catch{fail('READ_FAILED','原件读取失败，请稍后重试。');}
    // Revalidate after host IO so removed project references cannot leak a result.
    recheck(contextId,versionId,snapshot);
    if(blob!=null&&!(blob instanceof Blob))fail('INVALID_HOST_RESULT','宿主没有返回有效的原文件。');
    return blob??null;
  }

  async function getMaterial({contextId,versionId}){
    const snapshot=lookup(contextId,versionId),{doc,text}=snapshot;
    const blob=await load(contextId,versionId,snapshot);
    const originalStatus=!blob?'missing':blob.size>MATERIAL_LIMITS.originalBytes?'too_large':'available';
    const textStatus=text!=null?(text.length>MATERIAL_LIMITS.textChars?'too_large':'available'):
      !blob?'missing':!textFile(doc)?'not_extracted':originalStatus==='available'?'pending_read':originalStatus;
    return {
      api:'lifehub.workstation.material@1',materialId:doc.materialId||doc.id,
      versionId:doc.id,versionNumber:doc.version??1,contextId:doc.projectId,name:doc.name,
      previousVersionId:typeof doc.previousId==='string'&&validId(doc.previousId)?doc.previousId:null,
      sourceId:typeof doc.sourceId==='string'&&validId(doc.sourceId)?doc.sourceId:null,
      contentHash:typeof doc.sha==='string'&&/^[a-f\d]{64}$/i.test(doc.sha)?doc.sha:null,
      integrity:'not_checked',
      original:{artifactId:'original:'+doc.id,status:originalStatus,bytes:blob?.size??null,mimeType:blob?.type||doc.type||'application/octet-stream'},
      text:{artifactId:'text:'+doc.id,status:textStatus,origin:text!=null?'saved':blob&&textFile(doc)?'original':null}
    };
  }

  async function readArtifact({contextId,artifactId}){
    if(typeof artifactId!=='string')fail('INVALID_ID','产物标识无效。');
    const match=/^(original|text):(.+)$/.exec(artifactId);
    if(!match)fail('INVALID_ID','产物标识无效。');
    const [,kind,versionId]=match,snapshot=lookup(contextId,versionId);
    if(kind==='text'&&snapshot.text!=null){
      if(snapshot.text.length>MATERIAL_LIMITS.textChars)fail('TOO_LARGE','正文超过 120,000 字符，请拆分材料。');
      return {artifactId,versionId,kind,mimeType:'text/plain',content:snapshot.text};
    }
    const blob=await load(contextId,versionId,snapshot);
    if(!blob)fail('MISSING_ORIGINAL','原文件缺失，已保存的材料记录仍可保留。');
    if(kind==='text'&&!textFile(snapshot.doc))fail('NOT_EXTRACTED','此文件尚未提取正文，请补充正文或等待解析适配。');
    if(blob.size>MATERIAL_LIMITS.originalBytes)fail('TOO_LARGE','本阶段只读取不超过 2 MiB 的原件，请拆分材料。');
    if(kind==='original')return {artifactId,versionId,kind,mimeType:blob.type||'application/octet-stream',content:blob};
    let text;
    try{text=new TextDecoder('utf-8',{fatal:true}).decode(await blob.arrayBuffer());}
    catch{fail('UNSUPPORTED_ENCODING','无法按 UTF-8 读取正文，请转换编码后重试。');}
    recheck(contextId,versionId,snapshot);
    if(text.length>MATERIAL_LIMITS.textChars)fail('TOO_LARGE','正文超过 120,000 字符，请拆分材料。');
    return {artifactId,versionId,kind,mimeType:'text/plain',content:text};
  }

  return Object.freeze({getMaterial,readArtifact});
}
