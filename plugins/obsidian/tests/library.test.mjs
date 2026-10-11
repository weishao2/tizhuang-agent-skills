import test from 'node:test';
import assert from 'node:assert/strict';
import {Store,noteText,readNote,questionFrom} from '../src/core.js';
import {LocalCatalog} from '../src/library-core.js';
import {cleanTitle,enrichQuestion} from '../src/presentation.js';
import {harness} from './ui-harness.mjs';

function fixture(){
 const files=new Map([['题目库',null],['.bank/config.json',JSON.stringify({schema:'tizhuang.bank/v1',ui_layout:'teacher/v2'})]]);
 const io={exists:async p=>files.has(p),mkdir:async p=>files.set(p,null),read:async p=>files.get(p),write:async(p,v)=>files.set(p,v),list:async p=>({files:[...files.keys()].filter(k=>k.startsWith(p+'/')&&files.get(k)!==null)})};return{files,io,store:new Store(io)};
}
const q=(id,scope={})=>({schema:'tizhuang.question/v1',id,title:'一道数学题',content:'原题 $x=2$。',answer:'PRIVATE_ANSWER',analysis:'原解析',tags:['用途/课堂例题'],status:'draft',type:'选择题',score:5,subject_id:2,phase_id:2,edition_id:142,chapter_ids:['11'],knowledge_tree_ids:['2'],knowledge_ids:[],source:{kind:'local'},...scope});
test('本地树按学段教材隔离，父节点和标签层级检索不重复题目',async()=>{
 const h=fixture();h.files.set('.bank/taxonomy/2-2.json',JSON.stringify({subject_id:2,phase_id:2,nodes:[{id:1,name:'数与式',parent_id:0},{id:2,name:'乘方',parent_id:1}]}));h.files.set('.bank/textbooks/2-2-142.json',JSON.stringify({subject_id:2,phase_id:2,edition_id:142,nodes:[{id:10,name:'第1章',parent_id:0},{id:11,name:'第一节',parent_id:10}]}));
 h.files.set('题目库/数学/题1.md',noteText(q('q1')));h.files.set('题目库/另一版/题2.md',noteText(q('q2',{edition_id:59,phase_id:3})));
 const c=await new LocalCatalog(h.store).load();assert.equal(c.select({kind:'knowledge',scope:'2-2',node:'1'}).length,1);assert.equal(c.select({kind:'chapter',scope:'2-2-142',node:'10'}).length,1);assert.equal(c.select({tag:'用途'}).length,2);assert.equal(c.select({kind:'chapter',scope:'2-2-59',node:'10'}).length,0);assert.equal(c.tagTree().find(t=>t.id==='用途').ids.size,2);
});
test('原生 tags 是唯一编辑来源，分类保留答案与老师批注并备份',async()=>{
 const h=fixture();h.files.set('.bank/taxonomy/2-2.json',JSON.stringify({subject_id:2,phase_id:2,nodes:[{id:2,name:'乘方',knowledge_id:90}]}));const path='题目库/题1.md';h.files.set(path,noteText(q('q1'))+'\n## 老师笔记\nKEEP_ME');const c=await new LocalCatalog(h.store).load();
 await c.classify(path,{tags:['用途/复习'],knowledge:['2']});const after=readNote(h.files.get(path));assert.deepEqual(after.tags,['用途/复习']);assert.deepEqual(after.knowledge_ids,['90']);assert.equal(after.answer,'PRIVATE_ANSWER');assert.ok(h.files.get(path).includes('KEEP_ME'));assert.ok([...h.files.keys()].some(p=>p.startsWith('.bank/backups/')));await assert.rejects(c.classify(path,{tags:[],knowledge:['999']}),/不属于/);
});
test('图片与截断图片地址不成为标题；知识标签仅匹配唯一真实节点',()=>{
 assert.equal(cleanTitle('![配图](https://site/image.png) 求矩形面积'),'求矩形面积');assert.equal(cleanTitle('![](https://site/verylong'),'题目（见原图）');assert.equal(cleanTitle('条件 \\[\\]'),'条件');
 const value=q('q1',{chapter_ids:['11'],knowledge_tree_ids:[],original_payload:{knowledges:'乘方,重名'}});enrichQuestion(value,[{id:2,name:'乘方',knowledge_id:90},{id:3,name:'重名'},{id:4,name:'重名'}]);assert.deepEqual(value.knowledge_tree_ids,['2']);assert.deepEqual(value.knowledge_ids,['90']);assert.equal(value.edition_id,142);
});
test('本地工作台展示首页、图片标记和筛选，不请求网站或额度',async()=>{
 const h=harness(),p=new h.default();await p.onload();await p.store.init();const question=q('q1',{title:'![图](https://test.invalid/p.png) 图题',content:'![原图](Assets/'+'a'.repeat(64)+'.png)'});h.files.set('题目库/图题.md',noteText(question));h.files.set('.bank/imports',null);h.files.set('.bank/imports/abcdef123456abcdef123456/manifest.json',JSON.stringify({id:'abcdef123456abcdef123456',filename:'扫描卷.pdf',status:'needs_agent',pages:[{}],questions:[],imported:{}}));h.files.set('待整理/扫描卷.pdf · abcdef.md','# 报告');const view=new h.LibraryView({app:h.app},p);await view.onOpen();assert.equal(h.calls.length,0);assert.ok(view.contentEl.textContent.includes('好题，都在这里'));assert.ok(view.contentEl.textContent.includes('待 Agent 识别'));await [...view.contentEl.querySelectorAll('button')].find(b=>b.textContent==='查看报告').onclick();assert.equal(h.app.opened,'待整理/扫描卷.pdf · abcdef.md');await view.show('questions',{});assert.equal(view.contentEl.querySelectorAll('.tz-local-card').length,1);assert.ok(view.contentEl.querySelector('.tz-local-title').textContent.startsWith('[图]'));assert.ok(!view.contentEl.querySelector('.tz-local-title').textContent.includes('https'));const search=view.contentEl.querySelector('input[type=search]');search.value='不存在';search.dispatchEvent(new h.dom.window.Event('input'));await new Promise(r=>setTimeout(r,200));assert.equal(view.contentEl.querySelectorAll('.tz-local-card').length,0);assert.equal(h.calls.length,0);await view.onClose();
});

test('自动分类后首页按真实知识点归组，不受旧待分类文件夹影响',async()=>{
 const h=fixture();h.files.set('.bank/taxonomy/2-2.json',JSON.stringify({subject_id:2,phase_id:2,nodes:[{id:1,name:'数与式',parent_id:0},{id:2,name:'乘方',parent_id:1}]}));h.files.set('题目库/待分类/原名.md',noteText(q('q1')));
 const c=await new LocalCatalog(h.store).load();await c.writeHome();const home=h.files.get('题库首页.md');assert.ok(home.includes('数与式（1）'));assert.ok(!home.includes('### 待分类'));assert.ok(h.files.has('题目库/待分类/原名.md'));
});

test('老师修改知识点同步更新 Agent 生成的关联链接，清空后没有旧链接',async()=>{
 const h=fixture();h.files.set('.bank/taxonomy/2-2.json',JSON.stringify({subject_id:2,phase_id:2,nodes:[{id:2,name:'乘方',knowledge_id:90},{id:3,name:'整式',knowledge_id:91}]}));h.files.set('.bank/ui-paths.json',JSON.stringify({knowledge:{'2-2':{'3':'资料/整式.md'}}}));
 const path='题目库/原题.md';h.files.set(path,noteText(q('q1'))+'\n<!-- bank:knowledge:start -->\n## 知识点分类\n\n- [[资料/乘方|乘方]]\n<!-- bank:knowledge:end -->\n## 老师批注\nKEEP_ME');const c=await new LocalCatalog(h.store).load();
 await c.classify(path,{tags:['我的标签'],knowledge:['3']});assert.ok(h.files.get(path).includes('[[资料/整式|整式]]'));assert.ok(!h.files.get(path).includes('[[资料/乘方|乘方]]'));assert.ok(h.files.get(path).includes('KEEP_ME'));
 await c.classify(path,{tags:[],knowledge:[]});assert.ok(!h.files.get(path).includes('bank:knowledge:'));assert.ok(!h.files.get(path).includes('[[资料/整式|整式]]'));assert.equal(readNote(h.files.get(path)).content,q('q1').content);
});
