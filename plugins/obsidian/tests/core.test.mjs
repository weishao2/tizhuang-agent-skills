import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,mkdir,readdir,stat,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {Api,Store,requireScope,validateChapters,questionFrom,noteText,readNote,localize,hash,BASE} from '../src/core.js';
import {MetadataCache} from '../src/metadata-cache.js';
const s={subject_id:2,phase_id:2,edition_id:59,chapter_id:10,grade_id:201};
const nodes=[{id:10,name:'第一章',parent_id:0,subject_id:2,phase_id:2,edition_id:59,grade_id:201}];
const raw={id:100,subject_id:2,grade_id:200,title:'测试夹具：一次函数',options:{B:'保留首项',A:'保留次项'},answer:'主答案',analysis:'主解析',subquestions:[{title:'子题',answer:'子答案',analysis:'子解析'}]};
const convert=x=>String(x).replace(/<[^>]+>/g,'');
test('自己的凭证才可查询额度/题目，公开元数据不携带凭证',async()=>{
 const calls=[];let key='';const api=new Api(async p=>{calls.push(p);return {status:200,json:[]};},()=>key);
 await assert.rejects(api.quota(),/自己的/);assert.equal(calls.length,0);
 key='test-key';await api.meta('subjects');assert.deepEqual(calls[0].headers,{});await api.quota();assert.equal(calls[1].headers['X-API-Key'],key);assert.ok(calls.every(c=>c.url.startsWith(BASE)));
});
test('按用户实际选择的教材章节取题，无静默扩大/自动重试',async()=>{
 const calls=[];const api=new Api(async p=>{calls.push(p);return {status:200,json:p.url.includes('/quota')?{remaining:6}:{items:[raw]}};},()=> 'own-key');
 await api.questions(s,nodes,5);const url=new URL(calls[1].url);for(const [k,v]of Object.entries(s))if(k!=='phase_id')assert.equal(url.searchParams.get(k),String(v));assert.equal(url.searchParams.get('limit'),'5');assert.equal(url.searchParams.get('random_order'),'false');
 await assert.rejects(api.questions({...s,edition_id:142},nodes,5),/不属于/);assert.equal(calls.length,2);
 await assert.rejects(api.questions(s,nodes,7),/不足/);assert.equal(calls.length,3);
});
test('401、429 和收费网络结果不确定均不重试',async()=>{
 for(const status of [401,429,503]){let n=0;const api=new Api(async()=>{n++;return {status,json:{}};},()=> 'own');await assert.rejects(api.get('/v1/questions',{},true));assert.equal(n,1);}
 const api=new Api(async()=>{throw Error('socket token');},()=> 'own');await assert.rejects(api.get('/v1/questions',{},true),/可能已经扣额/);
});
test('目录和付费取题等待有期限，超时不重试、不缓存迟到响应',async()=>{
 let calls=0,resolve;const api=new Api(()=>{calls++;return new Promise(r=>{resolve=r;});},()=> 'own',{timeouts:{metadata:10,questions:10}});
 await assert.rejects(api.meta('chapters',{edition_id:59}),e=>e.code==='request_timeout'&&/可以继续切换/.test(e.message));assert.equal(calls,1);
 resolve({status:200,json:[{id:1}]});await Promise.resolve();assert.equal(api.cache.entries.size,0);
 await assert.rejects(api.get('/v1/questions',{},true),/可能已经扣额.*不会自动重试/);assert.equal(calls,2);
});
test('公共目录缓存跨重启复用、按范围隔离、过期和手动更新会重新请求',async()=>{
 const files=new Map(),io={exists:async p=>files.has(p),mkdir:async p=>files.set(p,null),read:async p=>files.get(p),write:async(p,v)=>files.set(p,v)};let now=100000,calls=0;
 const cache=new MetadataCache(io,{now:()=>now,ttl:1000});const loader=async()=>[{id:++calls,name:'公共目录'}];
 const first=await cache.get('chapters',{edition_id:59,subject_id:2},loader);first[0].name='caller edit';
 assert.equal((await cache.get('chapters',{subject_id:2,edition_id:'59'},loader))[0].name,'公共目录');assert.equal(calls,1);
 const reopened=new MetadataCache(io,{now:()=>now,ttl:1000});assert.equal((await reopened.get('chapters',{edition_id:59,subject_id:2},loader))[0].id,1);assert.equal(calls,1);
 await reopened.get('chapters',{edition_id:142,subject_id:2},loader);assert.equal(calls,2);
 await reopened.get('chapters',{edition_id:59,subject_id:2},loader,{force:true});assert.equal(calls,3);
 now+=1001;await reopened.get('chapters',{edition_id:59,subject_id:2},loader);assert.equal(calls,4);
 assert.ok([...files.values()].every(value=>value===null||(!value.includes('API-Key')&&!value.includes('quota'))));
});
test('相同目录请求合并，额度与付费题目每次实时查询',async()=>{
 let calls=0,finish;const api=new Api(async p=>{calls++;if(p.url.includes('/meta/'))return new Promise(resolve=>{finish=()=>resolve({status:200,json:[{id:2}]});});return{status:200,json:{remaining:10,items:[]}};},()=> 'own');
 const a=api.meta('subjects'),b=api.meta('subjects');await Promise.resolve();finish();assert.deepEqual(await a,await b);assert.equal(calls,1);
 await api.quota();await api.quota();await api.get('/v1/questions',{},true);await api.get('/v1/questions',{},true);assert.equal(calls,5);
});
test('目录缺失、循环、跨版本、截断均拒绝',()=>{
 assert.throws(()=>validateChapters([{...nodes[0],parent_id:999}],s));assert.throws(()=>validateChapters([{...nodes[0],parent_id:10}],s));assert.throws(()=>validateChapters([{...nodes[0],edition_id:142}],s));assert.throws(()=>validateChapters(Array(1000).fill(nodes[0]),s));assert.throws(()=>requireScope({...s,grade_id:202},nodes));
});
test('中文属性、顺序、母子题和答案分区符合共享协议',()=>{
 const q=questionFrom(raw,s,true,convert);assert.ok(q.content.indexOf('B. 保留首项')<q.content.indexOf('A. 保留次项'));assert.ok(!q.content.includes('子答案'));assert.ok(q.answer.includes('子答案'));assert.equal(q.grade_id,200);assert.deepEqual(q.chapter_ids,['10']);
 const text=noteText(q);assert.ok(text.includes('题目编号:'));assert.ok(text.includes('审核状态: 待核对'));assert.deepEqual(readNote(text).content,q.content);assert.equal(readNote(text).source.external_id,'100');
 const hidden=questionFrom(raw,s,false,convert);assert.equal(hidden.answer,'');assert.equal(hidden.analysis,'');assert.equal(hidden.original_payload.subquestions[0].answer,'');assert.equal(raw.subquestions[0].answer,'子答案');
});
test('图片归档哈希并且不携带用户 API Key；失败不污染可重试题目',async()=>{
 const q=questionFrom({...raw,title:'图片测试 ![](https://example.org/a.png)'},s,false,x=>x);const bytes=new Uint8Array([137,80,78,71]).buffer;const requests=[];
 const r=await localize(q,async p=>{requests.push(p);return {status:200,headers:{'content-type':'image/png'},arrayBuffer:bytes};});
 assert.deepEqual(requests[0].headers,{});assert.match(r.question.content,/Assets\/[a-f0-9]{64}\.png/);assert.equal(r.downloaded[0].sha256,await hash(bytes));assert.ok(q.content.includes('https://'));
 await assert.rejects(localize(q,async()=>{throw Error('offline');}));assert.ok(q.content.includes('https://'));
 await assert.rejects(localize({...q,content:'![](https://127.0.0.1/a.png)'},async()=>{}),/不受支持/);
});
function adapter(root){return {exists:async p=>{try{await stat(join(root,p));return true;}catch{return false;}},mkdir:p=>mkdir(join(root,p)),read:p=>readFile(join(root,p),'utf8'),write:(p,v)=>writeFile(join(root,p),v),writeBinary:(p,v)=>writeFile(join(root,p),new Uint8Array(v)),readBinary:async p=>{const b=await readFile(join(root,p));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);},list:async p=>{const entries=await readdir(join(root,p),{withFileTypes:true});return {files:entries.filter(e=>e.isFile()).map(e=>p+'/'+e.name),folders:entries.filter(e=>e.isDirectory()).map(e=>p+'/'+e.name)};}};}
test('保存不覆盖教师文件、按内容去重、来源冲突拒绝，并兼容本地 skill 检索组卷',async()=>{
 const root=await mkdtemp(resolve('.test-vault-'));try{
  const io=adapter(root),store=new Store(io),q=questionFrom(raw,s,true,convert);
  const result=await store.save(q,nodes,[]);assert.equal(result.action,'created');assert.equal((await store.save({...q,id:crypto.randomUUID()},nodes,[])).action,'duplicate');
  await assert.rejects(store.save({...q,id:crypto.randomUUID(),content:'新版本'},nodes,[]),/不会覆盖/);
  const existing=await io.read(result.path);await io.write(result.path,existing+'\n## 教师笔记\n手动添加\n');await store.save({...q,id:crypto.randomUUID()},nodes,[]);assert.ok((await io.read(result.path)).includes('手动添加'));
  const python=(process.env.TIZHUANG_TEST_PYTHON || 'python');
  const check=spawnSync(python,['tests/cross_skill.py',root],{encoding:'utf8'});assert.equal(check.status,0,check.stderr||check.stdout);assert.match(check.stdout,/cross-skill-ok/);
 }finally{await rm(root,{recursive:true,force:true});}
});
test('不兼容和旧英文仓库不能自动覆盖',async()=>{
 const root=await mkdtemp(resolve('.test-vault-'));try{const io=adapter(root);await io.mkdir('Questions');await assert.rejects(new Store(io).init(),/迁移/);}finally{await rm(root,{recursive:true,force:true});}
});
test('知识点左树保存格式也可被独立 skill 按父节点检索并组卷',async()=>{
 const root=await mkdtemp(resolve('.test-vault-'));try{
  const io=adapter(root),store=new Store(io);const scope={subject_id:2,phase_id:2,knowledge_tree_id:11};const tree=[{id:10,name:'函数',parent_id:0},{id:11,name:'一次函数',parent_id:10}];
  const q=questionFrom(raw,scope,true,convert);const result=await store.save(q,tree,[]);assert.equal(result.action,'created');assert.equal(q.edition_id,null);assert.deepEqual(q.chapter_ids,[]);
  const check=spawnSync((process.env.TIZHUANG_TEST_PYTHON || 'python'),['tests/cross_skill.py',root],{encoding:'utf8'});assert.equal(check.status,0,check.stderr||check.stdout);
 }finally{await rm(root,{recursive:true,force:true});}
});

test('保存双重分类的题目仍与独立 skill 检索互通',async()=>{
 const root=await mkdtemp(resolve('.test-vault-'));try{
  const store=new Store(adapter(root)),scope={...s,knowledge_tree_id:11},tree=[{id:9,name:'函数',parent_id:0},{id:11,name:'一次函数',parent_id:9}];
  const q=questionFrom(raw,scope,true,convert);await store.save(q,{chapters:nodes,knowledge:tree},[]);
  const check=spawnSync((process.env.TIZHUANG_TEST_PYTHON || 'python'),['tests/cross_skill_combined.py',root],{encoding:'utf8'});assert.equal(check.status,0,check.stderr||check.stdout);
 }finally{await rm(root,{recursive:true,force:true});}
});
