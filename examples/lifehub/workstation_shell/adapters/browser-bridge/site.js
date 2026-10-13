(() => {
 const allowed=new Set(['status','configure','collect','inbox','ack','poll','control','focus','frame','chat-start','chat-result']);
 window.addEventListener('message',async e=>{
  if(e.source!==window||e.origin!==location.origin||e.data?.channel!=='lifehub.bridge.v1'||e.data.direction!=='request'||!allowed.has(e.data.action)||typeof e.data.id!=='string')return;
  let result;try{result=await chrome.runtime.sendMessage({type:'station',action:e.data.action,payload:e.data.payload||{}});}catch(err){result={ok:false,error:err.message};}
  window.postMessage({channel:'lifehub.bridge.v1',direction:'reply',id:e.data.id,result},location.origin);
 });
})();
