import {findRunCommand,acceptRunCommand,readRun,RunCommandError} from '../domain/run-commands.js';

export function createRunCommandController({getState,commit,makeId,now}){
  if(typeof getState!=='function'||typeof commit!=='function')throw new TypeError('需要宿主提供运行状态和同步保存入口。');
  return Object.freeze({
    get:query=>readRun(getState(),query),
    accept(command){
      const previous=findRunCommand(getState(),command);
      if(previous)return previous;
      let receipt,error,entered=false,ok;
      try{
        ok=commit(()=>{
          if(entered)throw new RunCommandError('INVALID_HOST_RESULT','保存操作重复，请重新打开运行检查。');
          entered=true;
          try{
            const state=getState(),prepared=acceptRunCommand(state,command,{makeId,now});
            state.runs=prepared.state.runs;state.runCommands=prepared.state.runCommands;receipt=prepared.receipt;
          }catch(cause){error=cause;throw cause;}
        });
      }catch(cause){
        if(cause instanceof RunCommandError)throw cause;
        throw new RunCommandError('SAVE_FAILED','运行请求未能保存，请检查存储后重试。');
      }
      if(!entered||typeof ok!=='boolean')throw new RunCommandError('INVALID_HOST_RESULT','保存结果不可确认，请重新打开运行检查。');
      if(error)throw error;
      if(!ok)throw new RunCommandError('SAVE_FAILED','运行请求未能保存，请检查存储后重试。');
      return receipt;
    }
  });
}
