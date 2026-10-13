export const categories={lectures:'讲义',assignments:'作业',labs:'实验',announcements:'公告',notes:'笔记',other:'其他'};
export const checks={changed:'有更新',unchanged:'无变化',failed:'检查失败',pending:'尚未检查'};
export const runStates={ready:'待运行',queued:'待运行',running:'运行中',paused:'已暂停',waiting:'等待处理',completed:'已完成',failed:'失败',pending:'待执行',done:'已完成'};
export function safeHref(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}}
export function when(value){return value?new Date(value).toLocaleString('zh-CN',{timeZone:'America/Toronto',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}):'尚未检查';}
export function latestCheck(state,sourceId){return (state.checks||[]).filter(c=>!sourceId||c.sourceId===sourceId).slice().sort((a,b)=>(b.time||'').localeCompare(a.time||''))[0];}
export function readingState(state,d){return state.documentTexts[d.id]?.trim()?'ready':d.readingState==='failed'?'failed':'unread';}
