import {mkdir,writeFile} from 'node:fs/promises';

// Fixed content viewports rendered by the browser; scales only fit the QA display.
const directory=new URL('./qa/',import.meta.url);
await mkdir(directory,{recursive:true});
for(const [width,height,scale] of [[1600,900,.8],[1440,900,.9],[1280,800,1]]){
 const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>LifeHub QA ${width}×${height}</title><style>html,body{margin:0;overflow:hidden}iframe{display:block;border:0;width:${width}px;height:${height}px;transform:scale(${scale});transform-origin:0 0}</style></head><body><iframe title="工作区 ${width}×${height}" src="../index.html"></iframe></body></html>\n`;
 await writeFile(new URL(`${width}.html`,directory),html);
}
console.log('Wrote QA wrappers: fixed 1600×900, 1440×900 and 1280×800 content viewports.');
