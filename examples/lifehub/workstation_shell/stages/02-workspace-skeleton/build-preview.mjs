import {readFile,writeFile} from 'node:fs/promises';
import {workspaceSkeleton} from './skeleton.js';

const css=await readFile(new URL('./skeleton.css',import.meta.url),'utf8');
const license=await readFile(new URL('../../vendor/lucide-LICENSE.txt',import.meta.url),'utf8');
const html=`<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LifeHub · 第 02 步工作区骨架</title>
<!-- Selected Lucide icons; original notices retained below.
${license.replaceAll('--','—')}
-->
<style>${css}</style></head><body>${workspaceSkeleton()}</body></html>\n`;
await writeFile(new URL('./index.html',import.meta.url),html);
console.log('Wrote stages/02-workspace-skeleton/index.html (static; no runtime JavaScript).');
