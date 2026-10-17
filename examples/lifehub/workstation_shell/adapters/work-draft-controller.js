import {saveWorkDraft,getWorkDraft,WorkDraftError} from '../domain/work-drafts.js';

// The existing host owns persistence and rollback (e.g. its synchronous change()).
export function createWorkDraftController({getState,commit,makeId,now}){
  if(typeof getState!=='function'||typeof commit!=='function')throw new TypeError('需要宿主提供状态和同步保存入口。');
  return Object.freeze({
    get:query=>getWorkDraft(getState(),query),
    save(command){
      let work,error,entered=false,ok;
      try{
        ok=commit(()=>{
          entered=true;
          try{
            const state=getState(),prepared=saveWorkDraft(state,command,{makeId,now});
            state.requests=prepared.state.requests;
            work=prepared.work;
          }catch(cause){error=cause;throw cause;}
        });
      }catch(cause){
        if(cause instanceof WorkDraftError)throw cause;
        throw new WorkDraftError('SAVE_FAILED','工作未能保存，之前保存的内容仍应由宿主保留。');
      }
      if(!entered||typeof ok!=='boolean')throw new WorkDraftError('INVALID_HOST_RESULT','宿主未返回同步保存结果。');
      if(error)throw error;
      if(!ok)throw new WorkDraftError('SAVE_FAILED','工作未能保存，请检查存储后重试。');
      return work;
    }
  });
}
