import test from 'node:test';
import assert from 'node:assert/strict';
import {Api,queryFilters,requireScope,questionFrom,readNote} from '../src/core.js';
import {findDirectoryTarget,openDirectory} from '../src/directory-navigation.js';
import {harness} from './ui-harness.mjs';

const scope={subject_id:2,phase_id:2,edition_id:59,grade_id:201};
const directory={chapters:[{id:10,name:'第一章',parent_id:0,subject_id:2,phase_id:2,edition_id:59,grade_id:201}],knowledge:[{id:1480,name:'函数',parent_id:0},{id:1489,name:'一次函数',parent_id:1480},{id:1500,name:'几何',parent_id:0}]};
const choose=(h,v,key,value)=>{v.inputs[key].value=String(value);v.inputs[key].dispatchEvent(new h.dom.window.Event('change'));};
async function settled(v){for(let i=0;i<150;i++){await new Promise(r=>setTimeout(r,1));if(!v.lock&&!v.loading)return;}throw Error('界面未结束加载');}
async function setup(){const h=harness(),p=new h.default();await p.onload();const v=new h.BankView({app:h.app},p);await v.onOpen();choose(h,v,'subject_id',2);choose(h,v,'phase_id',2);await settled(v);return{h,p,v};}
async function fetch(h,p,v){await p.setKey('local-test-key',false);v.count.value='1';const job=v.run(()=>v.fetch());for(let i=0;i<20&&!h.doc.querySelector('.test-modal');i++)await Promise.resolve();const modal=h.doc.querySelector('.test-modal');assert.ok(modal,v.status.textContent);[...modal.querySelectorAll('button')].find(b=>b.textContent==='确认获取并扣减额度').click();await job;}

test('章节和知识点二选一，留空时仍限定学段，数组为重复参数',async()=>{
 assert.deepEqual(queryFilters(scope,directory),{subject_id:2,edition_id:59,grade_id:201,knowledge_tree_ids:[1480,1500]});
 for(const selected of [{chapter_id:10},{knowledge_tree_id:1489}]){
   const query=queryFilters({...scope,...selected},directory);assert.equal(query.knowledge_tree_ids,undefined);
   for(const [key,value]of Object.entries({...scope,...selected}))if(key!=='phase_id')assert.equal(query[key],value);
 }
 const calls=[],api=new Api(async request=>{calls.push(request);return{status:200,json:request.url.includes('/quota')?{remaining:20}:{items:[]}};},()=> 'own');
 await api.questions(scope,directory,5);const url=new URL(calls[1].url);assert.deepEqual(url.searchParams.getAll('knowledge_tree_ids'),['1480','1500']);assert.equal(url.searchParams.has('chapter_id'),false);assert.equal(calls.length,2);
});
test('未选节点也校验必填学科学段，目录缺失及伪造节点不发收费请求',()=>{
 assert.throws(()=>queryFilters({...scope,chapter_id:10,knowledge_tree_id:1489},directory),/请选择其中一个/);
 assert.throws(()=>queryFilters({...scope,phase_id:null},directory),/学科和学段/);
 assert.throws(()=>queryFilters(scope,{chapters:[],knowledge:[]}),/尚未加载/);
 assert.throws(()=>requireScope({...scope,chapter_id:999},directory),/章节不属于/);
 assert.throws(()=>requireScope({...scope,knowledge_tree_id:999},directory),/知识点不属于/);
 assert.throws(()=>requireScope({...scope,edition_id:142,chapter_id:10,knowledge_tree_id:1489},directory),/章节不属于/);
});
test('无章节学期可取题、保存和恢复留空选择，不虚构章节或知识节点',async()=>{
 const {h,p,v}=await setup();choose(h,v,'edition_id',59);await settled(v);
 // A valid catalogue can have no chapters for a selected term.
 v.meta.grades.push({id:202,name:'七年级下'});v.options('grade_id',v.meta.grades);choose(h,v,'grade_id',202);await settled(v);
 assert.equal(v.inputs.chapter_id.options.length,1);assert.equal(v.scope.chapter_id,null);assert.equal(v.inputs.knowledge_tree_id.hidden,false);
 await fetch(h,p,v);assert.equal(v.batch.items.length,1,v.status.textContent);await v.run(()=>v.saveBatch());assert.equal(v.batch.items[0].saved,true,v.status.textContent);
 const url=new URL(h.calls.find(c=>c.url.includes('/questions')).url);assert.equal(url.searchParams.has('chapter_id'),false);assert.equal(url.searchParams.has('knowledge_tree_id'),false);assert.equal(url.searchParams.get('grade_id'),'202');
 const q=readNote(h.files.get(v.batch.items[0].path));assert.deepEqual(q.chapter_ids,[]);assert.deepEqual(q.knowledge_tree_ids,[]);assert.equal(q.edition_id,59);
 const again=new h.BankView({app:h.app},p);await again.onOpen();assert.equal(again.scope.chapter_id,null);assert.equal(again.inputs.chapter_id.value,'');assert.equal(again.inputs.knowledge_tree_id.value,'');assert.equal(again.batch.items[0].saved,true);assert.equal(h.calls.filter(c=>c.url.includes('/questions')).length,1);h.dom.window.close();
});
test('两个筛选均显示，选一个自动清空另一项，并恢复最后选择',async()=>{
 const {h,p,v}=await setup();choose(h,v,'edition_id',59);await settled(v);choose(h,v,'chapter_id',10);await settled(v);choose(h,v,'knowledge_tree_id',1489);await settled(v);
 assert.equal(v.chapterFields.hidden,false);assert.equal(v.knowledgeFields.hidden,false);assert.equal(v.scope.chapter_id,null);assert.equal(v.inputs.chapter_id.value,'');assert.equal(v.scope.knowledge_tree_id,1489);
 choose(h,v,'chapter_id',10);await settled(v);assert.equal(v.scope.knowledge_tree_id,null);assert.equal(v.inputs.knowledge_tree_id.value,'');
 choose(h,v,'knowledge_tree_id',1489);await settled(v);await fetch(h,p,v);await v.run(()=>v.saveBatch());assert.equal(v.batch.items[0].saved,true,v.status.textContent);
 const q=readNote(h.files.get(v.batch.items[0].path));assert.deepEqual(q.chapter_ids,[]);assert.deepEqual(q.knowledge_tree_ids,['1489']);assert.equal(q.edition_id,59);
 const url=new URL(h.calls.find(c=>c.url.includes('/questions')).url);assert.equal(url.searchParams.has('chapter_id'),false);assert.equal(url.searchParams.get('knowledge_tree_id'),'1489');
 const again=new h.BankView({app:h.app},p);await again.onOpen();assert.equal(again.scope.chapter_id,null);assert.equal(again.scope.knowledge_tree_id,1489);
 choose(h,v,'edition_id',142);await settled(v);assert.equal(v.scope.chapter_id,null);assert.equal(v.scope.knowledge_tree_id,1489);choose(h,v,'knowledge_tree_id','');await settled(v);assert.equal(v.scope.knowledge_tree_id,null);h.dom.window.close();
});
test('纯学科学段也可获取，清空教材不带旧章节，不强制重选节点',async()=>{
 const {h,p,v}=await setup();choose(h,v,'edition_id',59);await settled(v);choose(h,v,'chapter_id',10);choose(h,v,'edition_id','');await settled(v);assert.equal(v.scope.chapter_id,null);
 await fetch(h,p,v);await v.run(()=>v.saveBatch());assert.equal(v.batch.items[0].saved,true,v.status.textContent);const q=readNote(h.files.get(v.batch.items[0].path));assert.equal(q.edition_id,null);assert.deepEqual(q.chapter_ids,[]);h.dom.window.close();
});
test('定位按节点编号而非文件名，展开左侧并保留筛选，不取题',async()=>{
 const {h,p,v}=await setup();await v.applyContext({mode:'chapter',scope:{...scope,chapter_id:10}});
 const file={path:'资料/教材目录/数学/老师改过的标题.md',extension:'md'};h.files.set(file.path,'---\n章节编号: 10\n学科编号: 2\n学段编号: 2\n教材版本编号: 59\n---\n# 第一章');h.app.vault.getMarkdownFiles=()=>[file];
 const revealed=[],opened=[],explorer={view:{revealInFolder:async f=>revealed.push(f.path)}};
 h.app.workspace.getLeavesOfType=type=>type==='file-explorer'?[explorer]:[];h.app.workspace.getLeaf=()=>({openFile:async f=>{opened.push(f.path);h.events.get('file-open')(f);}});h.app.workspace.revealLeaf=async()=>{};
 const before=h.calls.length,saved=JSON.stringify(v.scope);await p.openDirectory(v,'chapter');assert.deepEqual(opened,[file.path]);assert.deepEqual(revealed,[file.path]);assert.equal(JSON.stringify(v.scope),saved);assert.equal(h.calls.length,before);assert.equal(p.routingDirectory,false);h.dom.window.close();
});
test('未选节点打开对应学科目录，缺失节点落到本地目录，不创建空白文件',async()=>{
 const {h,p,v}=await setup();const folder='资料/知识目录/初中数学';h.files.set(folder,null);h.files.set(folder+'/函数.md','---\n知识节点编号: 1480\n学科编号: 2\n学段编号: 2\n---\n# 函数');h.files.set(folder+'/知识树.md','# 知识树');h.app.vault.getMarkdownFiles=()=>[...h.files.keys()].filter(p=>p.endsWith('.md')).map(path=>({path,extension:'md'}));
 const result=await findDirectoryTarget(p,v.scope,'knowledge');assert.equal(result.file.path,folder+'/知识树.md');
 const missing=await findDirectoryTarget(p,{...v.scope,knowledge_tree_id:999},'knowledge');assert.equal(missing.exact,false);assert.equal(missing.file.path,result.file.path);
 const before=h.files.size;await assert.rejects(findDirectoryTarget(p,v.scope,'chapter'),/尚未下载/);assert.equal(h.files.size,before);h.dom.window.close();
});
