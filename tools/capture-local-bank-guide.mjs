// Actual bundled plugin components; in-memory examples, never a personal vault.
// Run after building plugins/obsidian. No vault, credentials or website calls.
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.chdir(path.join(root,'plugins/obsidian'));
const {harness}=await import('../plugins/obsidian/tests/ui-harness.mjs');
const {noteText}=await import('../plugins/obsidian/src/core.js');
const require=createRequire(import.meta.url),runtime=process.env.TZ_PREVIEW_NODE_MODULES;
const {chromium}=require(runtime?path.join(runtime,'playwright'):'playwright');
const {marked}=require(runtime?path.join(runtime,'marked'):'marked');
const out=path.join(root,'docs/local-bank/screenshots');await mkdir(out,{recursive:true});
const example=process.env.TZ_GUIDE_EXAMPLES?JSON.parse(await readFile(process.env.TZ_GUIDE_EXAMPLES,'utf8')):null;
const h=harness(),plugin=new h.default();await plugin.onload();await plugin.store.init();
h.app.vault.adapter.getBasePath=()=> 'D:/我的教学题库';
h.app.vault.getResourcePath=f=>example?.assets?.[f.path.split('/').at(-1)]||f.path;
h.renderer.render=async(app,text,el)=>{
 if(example)text=text.replace(/\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|(?<!\\)\$([^$\n]+?)(?<!\\)\$/g,(whole,...args)=>{
   const expression=args.slice(0,4).find(v=>v!==undefined);if(!expression.trim())return '';
   const decode=h.doc.createElement('textarea');decode.innerHTML=expression;
   assert(example.math[decode.value],'Unrendered expression: '+decode.value);return example.math[decode.value];
 });
 el.innerHTML=marked.parse(text);
};
const put=(p,v)=>h.files.set(p,typeof v==='string'?v:JSON.stringify(v));
put('.bank/config.json',{schema:'tizhuang.bank/v1',ui_layout:'teacher/v2'});
put('.bank/catalog/names.json',{subjects:{2:'数学'},phases:{2:'初中'},editions:{}});
const nodes=example?.nodes||[{id:1,name:'函数',parent_id:0},{id:2,name:'一次函数',parent_id:1},{id:3,name:'反比例函数',parent_id:1},{id:4,name:'方程与不等式',parent_id:0},{id:5,name:'一元一次方程',parent_id:4}];
put('.bank/taxonomy/2-2.json',{subject_id:2,phase_id:2,nodes});
const samples=[
 ['一次函数的函数值','已知一次函数 y = 2x + 1，求 x = 3 时的函数值。','7','把 x = 3 代入，得 y = 2 × 3 + 1 = 7。','填空题',2,'课堂例题'],
 ['一次函数与坐标轴的交点','直线 y = 2x − 4 与 x 轴、y 轴分别交于哪一点？','(2, 0)，(0, −4)','令 y = 0 得 x = 2；令 x = 0 得 y = −4。','解答题',2,'课后练习'],
 ['一次函数的变化趋势','对于函数 y = −3x + 2，y 随 x 的增大而增大。（判断对错）','错误','一次项系数小于 0，y 随 x 的增大而减小。','判断题',2,'课堂例题'],
 ['反比例函数的系数','点 (2, 6) 在反比例函数 y = k/x 的图象上，求 k。','12','代入得到 6 = k/2，所以 k = 12。','填空题',3,'课后练习'],
 ['一元一次方程求解','解方程：3x + 2 = 11。','x = 3','移项得 3x = 9，两边除以 3。','解答题',5,'课后练习'],
 ['待整理的自编练习','已知 y = 4x − 1，求 x = 2 时 y 的值。','7','代入可得 y = 4 × 2 − 1 = 7。','填空题',null,'课后练习']
];
const questions=example?.questions||samples.map(([title,content,answer,analysis,type,k,tag],i)=>({schema:'tizhuang.question/v1',id:'guide-demo-'+(i+1),title,content,answer,analysis,type,score:i===1?10:5,difficulty:2,status:i<3?'reviewed':'draft',subject_id:2,phase_id:2,edition_id:null,chapter_ids:[],knowledge_tree_ids:k?[String(k)]:[],knowledge_ids:[],tags:['用途/'+tag,'来源/自编示例'],source:{kind:'local',label:'使用说明自编示例'},assets:[],created_at:'2026-10-14T08:00:00Z',updated_at:'2026-10-14T08:00:00Z'}));
for(const q of questions)put('题目库/初中·数学/'+q.title+'.md',noteText(q));
const batch='0123456789abcdef01234567';
h.files.set('.bank/imports',null);h.files.set('.bank/imports/'+batch,null);
put('.bank/imports/'+batch+'/manifest.json',{id:batch,filename:'一次函数随堂练习（自编）.pdf',status:'prepared',pages:[{},{}],imported:{},created_at:'2026-10-14T09:00:00Z'});
put('待整理/一次函数随堂练习 · '+batch.slice(0,6)+'.md','# 自编 PDF 演示');
const view=new h.LibraryView({app:h.app},plugin);await view.onOpen();assert.equal(view.catalog.rows.length,questions.length);assert.equal(view.catalog.errors.length,0);
const snapshots=[];
function snapshot(name,el=view.contentEl,width=1100){
 for(const s of el.querySelectorAll('select'))for(const o of s.options)o.toggleAttribute('selected',o.selected);
 for(const i of el.querySelectorAll('input')){i.setAttribute('value',i.value);i.toggleAttribute('checked',i.checked);}
 for(const t of el.querySelectorAll('textarea'))t.textContent=t.value;
 for(const img of el.querySelectorAll('img')){const url=img.getAttribute('src');if(example?.assets?.[url])img.src=example.assets[url];assert(!img.src.startsWith('http'),'Remote image must be downloaded before capture');}
 snapshots.push({name,markup:el.outerHTML,width});
}
snapshot('01-home');
await plugin.basket.add(example? [questions[0],questions[2],questions[4]]:questions.slice(0,3));await plugin.basket.settings({title:example?'初中数学 · 图象与几何练习':'一次函数 · 随堂练习',duration_minutes:30,answer_space_mm:25});
await view.show('questions',{});view.dimension='knowledge';view.draw();
if(example){const expand=[...view.contentEl.querySelectorAll('button')].filter(b=>b.textContent==='展开题目')[2];await expand.onclick({currentTarget:expand});}
snapshot('03-knowledge');
view.dimension='tags';view.draw();snapshot('04-tags');
const classify=[...view.contentEl.querySelectorAll('button')].find(b=>b.textContent==='分类 / 标签');assert(classify);classify.click();
snapshot('05-classify',h.doc.querySelector('.test-modal'),760);h.doc.querySelector('.test-modal').remove();
await view.show('basket');
if(example){const detail=[...view.contentEl.querySelectorAll('button')].filter(b=>b.textContent==='查看原题与答案')[2];await detail.onclick({currentTarget:detail});}
snapshot('07-basket');
plugin.basket.data.last_result={student_docx:'D:/我的教学题库/试卷/示例/打印稿/试卷.docx',teacher_docx:'D:/我的教学题库/试卷/示例/教师稿/试卷.docx',student:'D:/我的教学题库/试卷/示例/打印稿/试卷.html',teacher:'D:/我的教学题库/试卷/示例/教师稿/试卷.html',note:'D:/我的教学题库/试卷/示例/试卷.md'};
view.draw();snapshot('08-word-output');
plugin.settings.lastPdfScope={subject_id:2,phase_id:2};
plugin.store.io.writeBinary=async(p,bytes)=>h.files.set(p,bytes);
plugin.runLocal=async command=>{assert.equal(command,'pdf-prepare');return {batch,status:'prepared',imported:0,report:'待整理/一次函数随堂练习 · 012345.md'};};
await view.show('pdf');
const file=view.contentEl.querySelector('input[type=file]');Object.defineProperty(file,'files',{value:[{name:'一次函数随堂练习（自编）.pdf',size:50,arrayBuffer:async()=>new TextEncoder().encode('%PDF-self-authored-demo').buffer}]});file.onchange();
await [...view.contentEl.querySelectorAll('button')].find(b=>b.textContent==='准备导入').onclick();
assert(view.contentEl.textContent.includes('已保存原页'));snapshot('06-pdf');
const bank=new h.BankView({app:h.app},plugin);bank.draw();bank.scope=example?.website.scope||{subject_id:2,phase_id:2,knowledge_tree_id:2};bank.mode='knowledge';bank.meta={subjects:[{id:2,name:'数学'}],phases:[{id:2,name:'初中'}],editions:[],grades:[]};bank.knowledgeNodes=nodes;
for(const [key,values,label]of [['subject_id',bank.meta.subjects],['phase_id',bank.meta.phases],['edition_id',[],'不限教材版本'],['grade_id',[],'全部年级 / 学期'],['chapter_id',[],'不限章节'],['knowledge_tree_id',nodes,'不限知识点']])bank.options(key,values,label);
bank.advanced.open=true;bank.count.value='2';bank.solutions.checked=true;bank.updateContext();bank.showQuota(example?.quota.remaining??20,example?.quota.used??0);
bank.batch={scope:{...bank.scope},nodes:{chapters:[],knowledge:nodes},solutions:true,items:example?example.website.items.map(raw=>({selected:true,saved:false,raw})):questions.slice(0,2).map((q,i)=>({selected:true,saved:false,raw:{id:900001+i,subject_id:2,title_html:q.content,question_type:q.type,difficulty:q.difficulty,knowledges:'一次函数',answer_html:q.answer,analysis_html:q.analysis,source:'图文说明自编演示，非网站题目',subquestions:[]}}))};
await bank.renderBatch();bank.say('已获取 2 题。保存到本地不再扣额。');snapshot('02-website',bank.contentEl);
assert.equal(h.calls.length,0,'Guide must not contact a website or spend quota');
const css=await readFile('styles.css','utf8');
const base=`body{margin:0;font:15px/1.6 'Segoe UI','Microsoft YaHei',sans-serif;background:var(--background-primary);color:var(--text-normal)}button,input,select,textarea{font:inherit;color:inherit}button{cursor:pointer}.tz-bank{width:100%}.theme-light{color-scheme:light;--background-primary:#fafafd;--background-secondary:#f2f1f7;--background-modifier-border:#dedde7;--background-modifier-hover:#e7e5f0;--text-normal:#262331;--text-muted:#716c80;--text-faint:#878191;--text-error:#c62828;--interactive-accent:#7952df;--interactive-accent-hover:#6940d0;--text-on-accent:#fff}.test-modal{margin:28px;padding:28px;background:white;border:1px solid #dedde7;border-radius:16px}.tz-paper-success{margin:24px;padding:24px}.guide-caption{padding:12px 24px;color:#716c80;font-size:12px;border-bottom:1px solid #dedde7}input[type=checkbox]{accent-color:#8b5cf6}`;
const browser=await chromium.launch({headless:true,...(process.env.TZ_PREVIEW_BROWSER?{executablePath:process.env.TZ_PREVIEW_BROWSER}:{})});
const report=[];
try{for(const s of snapshots){const page=await browser.newPage({viewport:{width:s.width,height:900},deviceScaleFactor:1});await page.route('**/*',r=>r.abort());await page.setContent(`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>${base}\n${css}</style><body class="theme-light"><div class="guide-caption">插件 0.13.1 · ${example?'题庄接口真实题目 · 操作状态为演示':'离线演示界面 · 自编示例题'}</div>${s.markup}</body></html>`);await page.evaluate(()=>document.fonts.ready);const size=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight}));assert.equal(size.width,size.scroll,s.name+' overflow');assert(await page.locator('img').evaluateAll(imgs=>imgs.every(i=>i.complete&&i.naturalWidth>0)),s.name+' broken image');await page.screenshot({path:path.join(out,s.name+'.png'),fullPage:true});report.push({name:s.name,...size});await page.close();}}
finally{await browser.close();await view.onClose();h.dom.window.close();}
await writeFile(path.join(out,'capture.json'),JSON.stringify({renderer:'Actual plugin 0.13.1 components; simulated Obsidian APIs and workflow state, not a native app screenshot',data:example?'Real question content from authorized Tizhuang API retrieval; redacted in-memory demo dataset, not distributed in the empty vault':'Self-authored synthetic questions; in-memory fixture, no user vault or credentials',questionIds:example?questions.map(q=>q.source.external_id):[],networkRequestsDuringCapture:h.calls.length,screenshots:report},null,2)+'\n');
console.log(JSON.stringify({screenshots:report.length,networkRequests:h.calls.length,output:out}));
