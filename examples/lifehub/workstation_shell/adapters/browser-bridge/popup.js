const result=document.getElementById('result');
for(const action of ['bind','monitor','disconnect'])document.getElementById(action).addEventListener('click',async()=>{
 try{
  if(action==='bind'){const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const u=new URL(tab.url);if(!['https:','http:'].includes(u.protocol))throw Error('请选择普通网页。');const granted=await chrome.permissions.request({origins:[u.origin+'/*']});if(!granted)throw Error('没有获得这个来源的访问授权。');}
  result.textContent='正在处理…';const r=await chrome.runtime.sendMessage({type:'popup',action});if(!r.ok)throw Error(r.error);result.textContent={bind:'已绑定。回到工作站 → 来源 → 绑定页面。',monitor:'监控已启用。回到工作站 → 运行监控 → 开始预览。',disconnect:'所有绑定与轮询已断开。'}[action];
 }catch(e){result.textContent=e.message;}
});
