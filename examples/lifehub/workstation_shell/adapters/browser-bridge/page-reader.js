// Runs inside exactly one explicitly bound top-frame document; never evaluates page instructions.
export function readBoundPage(selector,expectedUrl){
 const cleanUrl=v=>{const u=new URL(v);u.hash='';return u.href;};
 if(cleanUrl(location.href)!==cleanUrl(expectedUrl))throw Error('页面地址已经改变，需要重新绑定。');
 if(document.readyState!=='complete')throw Error('页面尚未加载完整。');
 if(document.querySelector('input[type="password"]')||/\/(login|signin|sign-in|auth)(\/|$)/i.test(location.pathname))throw Error('来源需要登录，请接管处理。');
 if(selector.length>200)throw Error('读取范围过长。');
 const roots=[...document.querySelectorAll(selector)].filter(e=>e.getClientRects().length);
 if(roots.length!==1)throw Error('读取范围匹配到 '+roots.length+' 个可见区域，请调整 selector。');
 const root=roots[0],copy=root.cloneNode(true);copy.querySelectorAll('script,style,noscript,iframe,input,textarea,[contenteditable="true"]').forEach(e=>e.remove());
 const text=(root.innerText||'').trim();if(!text)throw Error('读取范围没有可见正文。');
 if(text.length>120000||copy.outerHTML.length>2000000)throw Error('页面过大，请缩小范围。');
 const links=[...root.querySelectorAll('a[href]')].map(a=>({title:a.innerText.trim(),url:a.href})).filter(a=>/^https?:/.test(a.url));
 return {status:'complete',scope:'bound-page',url:location.href,selector,title:document.title,text,html:'<!doctype html><meta charset="utf-8">'+copy.outerHTML,links,capturedAt:new Date().toISOString()};
}
export function pageCanRefresh(){
 if(document.querySelector('input[type="password"]'))throw Error('需要登录，不能自动刷新。');
 const fields=[...document.querySelectorAll('textarea,[contenteditable="true"],input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="button"]):not([type="submit"])')];
 if(fields.some(e=>e.getClientRects().length&&(e.value||e.innerText||'').trim()))throw Error('页面已有输入内容，已停止自动刷新，请接管处理。');
 return {url:location.href,ready:document.readyState==='complete'};
}
