import test from 'node:test';
import assert from 'node:assert/strict';
import {harness} from './ui-harness.mjs';
async function settled(view){for(let i=0;i<100;i++){await new Promise(resolve=>setTimeout(resolve,1));if(!view.lock&&!view.loading)return;}throw Error('view did not settle');}
function choose(h,view,key,value){view.inputs[key].value=String(value);view.inputs[key].dispatchEvent(new h.dom.window.Event('change'));}
test('本地题库标题与官网入口正确，凭证入口保留且不会向官网传递凭证',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();assert.equal(view.contentEl.querySelector('.tz-brand h2').textContent,'本地题库');assert.equal(view.getDisplayText(),'题庄本地题库');
 const opened=[];h.dom.window.open=(...args)=>opened.push(args);const before=h.calls.length;view.contentEl.querySelector('.tz-website').click();assert.deepEqual(opened,[['https://tizhuang.qcscience.cc/','_blank','noopener,noreferrer']]);assert.equal(h.calls.length,before);
 let settings;h.app.setting.openTabById=id=>{settings=id;};const credentials=view.contentEl.querySelector('button[aria-label="设置自己的凭证"]');assert.ok(credentials.closest('.tz-balance'));credentials.click();assert.equal(settings,'tizhuang-question-bank');h.dom.window.close();
});
test('难度中文分组覆盖边界、缺失和异常值，保留原始数值',()=>{
 const h=harness(),plugin=new h.default(),view=new h.BankView({app:h.app},plugin);
 for(const [value,label]of [[0,'简单'],[2,'简单'],[2.5,'中等'],[3,'中等'],[3.99,'中等'],[4,'困难'],[5,'困难'],[null,null],[-1,null],[6,null],[NaN,null],['3',null]]){const raw={difficulty:value};assert.equal(view.questionMetadata(raw).difficultyLabel,label);assert.ok(Object.is(raw.difficulty,value));}h.dom.window.close();
});
test('详情按需展开来源与答案解析，收起和保存重绘保留勾选，不再请求额度或取题',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();await view.applyContext({mode:'chapter',scope:{subject_id:2,phase_id:2,edition_id:59,chapter_id:10}});
 const raw={id:12,subject_id:2,title_html:'例题 x<sup>2</sup>',question_type:'判断题',difficulty:0,knowledges:'相反数,乘方,相反数',year:2016,area:'广东省',source:'某校七年级期中卷',answer_html:'<b>×</b><script>steal()</script>',analysis_html:'判断 $x_1^2$。'};
 view.batch={scope:{...view.scope},nodes:structuredClone(view.nodes),solutions:true,items:[{raw,selected:true,saved:false}]};const renders=[],renderer=h.renderer.render;h.renderer.render=async(app,text,el,...rest)=>{renders.push(text);return renderer(app,text,el,...rest);};await view.renderBatch();const before=h.calls.length;
 const card=view.results.querySelector('.tz-question'),toggle=card.querySelector('.tz-detail-toggle'),region=card.querySelector('.tz-question-details');assert.equal(region.hidden,true);assert.equal(toggle.getAttribute('aria-expanded'),'false');assert.equal(renders.length,1);assert.equal(card.querySelector('.tz-difficulty').textContent,'简单');assert.equal(card.querySelector('.tz-local-status').textContent,'未保存');assert.equal(card.querySelector('.tz-knowledge').textContent,'相反数 · 乘方');
 toggle.click();await new Promise(r=>setTimeout(r,0));assert.equal(region.hidden,false);assert.equal(toggle.getAttribute('aria-expanded'),'true');assert.equal(toggle.getAttribute('aria-controls'),region.id);assert.match(region.textContent,/广东省/);assert.match(region.textContent,/2016/);assert.match(region.textContent,/某校七年级期中卷/);assert.equal(region.querySelector('dl'),null);assert.ok(!region.textContent.includes('取题范围'));assert.equal(region.lastElementChild.className,'tz-source-line');assert.deepEqual([...region.lastElementChild.children].map(e=>e.textContent),['2016','广东省','某校七年级期中卷','12']);assert.ok(region.textContent.includes('$x_1^2$'));assert.ok(!region.textContent.includes('steal'));assert.equal(renders.length,3);
 card.querySelector('input').click();assert.equal(view.batch.items[0].selected,false);assert.equal(region.hidden,false);toggle.click();assert.equal(region.hidden,true);toggle.click();await new Promise(r=>setTimeout(r,0));assert.equal(renders.length,3);assert.equal(view.batch.items[0].selected,false);
 view.batch.items[0].saved=true;view.batch.items[0].path='题目库/例题.md';await view.renderBatch();assert.equal(view.results.querySelector('.tz-question-details').hidden,false);assert.equal(view.results.querySelector('.tz-local-status').textContent,'已保存');assert.equal(view.results.querySelector('.tz-question input').disabled,true);assert.equal(h.calls.length,before);h.dom.window.close();
});
test('未勾选答案解析和网站缺失字段均如实提示，不虚构难度、来源或答案',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();const item={raw:{id:13,subject_id:2,title:'例题',difficulty:9,answer_html:'不应展示的答案',analysis_html:'不应展示的解析'},selected:true,saved:false};
 view.batch={scope:{subject_id:2},nodes:[],solutions:false,items:[item]};await view.renderBatch();const before=h.calls.length;view.results.querySelector('.tz-detail-toggle').click();await new Promise(r=>setTimeout(r,0));let details=view.results.querySelector('.tz-question-details');assert.equal(view.results.querySelector('.tz-difficulty'),null);assert.equal(details.querySelector('dl'),null);assert.equal(details.querySelector('.tz-source-line').textContent,'13');assert.match(details.textContent,/本次未包含答案解析/);assert.ok(!details.textContent.includes('不应展示'));assert.equal(h.calls.length,before);
 view.batch.solutions=true;item.raw.answer_html='';item.raw.analysis_html='';await view.renderBatch();details=view.results.querySelector('.tz-question-details');assert.match(details.textContent,/网站未提供答案/);assert.match(details.textContent,/网站未提供解析/);assert.equal(h.calls.length,before);h.dom.window.close();
});
test('勾选和全选联动保存数量，已保存题目不可再次保存，原始题型不猜测',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();
 view.batch={scope:{subject_id:2,phase_id:2,edition_id:59,chapter_id:10},nodes:[],solutions:false,items:[{raw:{id:1,title_html:'第一道',question_type:'选择题'},selected:true,saved:false},{raw:{id:2,title_html:'第二道',question_type:'判断题'},selected:true,saved:false},{raw:{id:3,title_html:'已保存'},selected:true,saved:true,path:'题目库/已保存.md'}]};await view.renderBatch();
 assert.equal(view.saveButton.textContent,'保存到本地 (2)');assert.equal(view.selectAll.checked,true);const checks=view.results.querySelectorAll('.tz-question input');assert.equal(checks[2].disabled,true);
 checks[0].click();assert.equal(view.batch.items[0].selected,false);assert.equal(view.saveButton.textContent,'保存到本地 (1)');assert.equal(view.selectAll.indeterminate,true);
 view.selectAll.click();assert.equal(view.selectAll.checked,true);assert.equal(checks[0].checked,true);view.selectAll.click();assert.equal(view.saveButton.disabled,true);assert.equal(view.batch.items[2].selected,true);
 view.setDisabled(false);assert.equal(view.saveButton.disabled,true);assert.equal(checks[2].disabled,true);checks[1].click();assert.equal(view.saveButton.disabled,false);assert.equal(view.selectionLabel.textContent,'已选 1 / 2');
 view.setDisabled(true);assert.equal(view.saveButton.disabled,true);assert.equal(view.selectAll.disabled,true);view.lock=false;view.setDisabled(false);assert.equal(view.saveButton.disabled,false);
 assert.deepEqual([...view.results.querySelectorAll('.tz-type')].map(e=>e.textContent),['选择题','判断题','未分类']);assert.ok(!view.results.textContent.includes('网站题号'));assert.ok(!view.results.textContent.includes('选择此题'));assert.equal(h.calls.filter(c=>c.url.includes('/questions')).length,0);h.dom.window.close();
});
test('真实面板代码：中文菜单、级联清空、收费确认、可重试保存，无二次取题',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();assert.equal(view.getDisplayText(),'题庄本地题库');assert.equal(plugin.commands[0].name,'打开本地题库');
 choose(h,view,'subject_id',2);choose(h,view,'phase_id',2);await settled(view);choose(h,view,'edition_id',59);await settled(view);choose(h,view,'chapter_id',10);
 choose(h,view,'edition_id',142);await settled(view);assert.equal(view.scope.chapter_id,null);assert.equal(view.inputs.chapter_id.value,'');choose(h,view,'edition_id',59);await settled(view);choose(h,view,'chapter_id',10);view.count.value='1';
 await view.run(()=>view.fetch());assert.match(view.status.textContent,/自己的/);assert.equal(h.calls.filter(c=>c.url.includes('/questions')).length,0);
 await plugin.setKey('fixture-own-key',false);const fetching=view.run(()=>view.fetch());await Promise.resolve();const modal=h.doc.querySelector('.test-modal');assert.ok(modal.textContent.includes('确认获取并扣减额度'));[...modal.querySelectorAll('button')].find(b=>b.textContent==='确认获取并扣减额度').click();await fetching;
 assert.equal(view.batch.items.length,1);assert.ok(view.results.textContent.includes('B. 第二项'));assert.ok(!view.results.textContent.includes('steal'));assert.ok(view.batch.items[0].raw.title_html.includes('script'));
 const realSave=plugin.store.save.bind(plugin.store);plugin.store.save=async()=>{throw Error('模拟磁盘故障');};await view.run(()=>view.saveBatch());assert.ok(!view.batch.items[0].saved);assert.match(view.status.textContent,/无需重新取题/);
 plugin.store.save=realSave;await view.run(()=>view.saveBatch());assert.ok(view.batch.items[0].saved);assert.equal(h.calls.filter(c=>c.url.includes('/questions')).length,1);
 const reopened=new h.BankView({app:h.app},plugin);await reopened.onOpen();assert.ok(reopened.batch.items[0].saved);assert.match(reopened.status.textContent,/恢复/);assert.equal(reopened.scope.chapter_id,10);assert.equal(reopened.count.value,'1');assert.equal(h.calls.filter(c=>c.url.includes('/questions')).length,1);assert.ok(!h.files.get('.bank/pending/questions.json').includes('fixture-own-key'));
 const saved=[...h.files.entries()].find(([k])=>k.startsWith('题目库/')&&k.endsWith('.md'));assert.ok(saved[1].includes('教材版本编号: 59'));assert.ok(!saved[1].includes('fixture-own-key'));assert.equal(h.calls.find(c=>c.url.includes('/questions')).headers['X-API-Key'],'fixture-own-key');
 h.dom.window.close();
});
test('凭证仅存 Obsidian 密钥存储引用；旧版只使用会话内存',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();await plugin.setKey('private-fixture-key',true);assert.ok(!plugin.saved.includes('private-fixture-key'));assert.equal(plugin.getKey(),'private-fixture-key');assert.equal(h.secrets.size,1);await plugin.clearKey();assert.equal(plugin.getKey(),'');
 delete h.app.secretStorage;await plugin.setKey('session-key',true);assert.equal(plugin.getKey(),'session-key');assert.ok(!plugin.saved.includes('session-key'));plugin.onunload();assert.equal(plugin.getKey(),'');h.dom.window.close();
});
test('数学表达式保留 TeX 反斜线、下标、上下标 HTML，不被 Markdown 转换改写',()=>{
 const h=harness();const tex=String.raw`$y=\frac{x_1}{2}$`;assert.equal(h.markdown('<p>'+tex+'</p>'),tex);assert.equal(h.markdown(String.raw`\(x_1\)`),'$x_1$');assert.ok(h.markdown('x<sup>2</sup> + a<sub>1</sub>').includes('<sup>2</sup>'));h.dom.window.close();
});
test('左树章节/知识点带入同一面板，记住范围和开关，点击节点不扣额',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();h.app.workspace.getLeavesOfType=()=>[{view}];
 const file={path:'教材目录/第一章.md',extension:'md'};h.frontmatter.set(file.path,{'章节编号':'10','学科编号':2,'学段编号':2,'教材版本编号':59,'年级编号':201});h.app.activeFile=file;
 await plugin.useActiveFile(view);assert.equal(view.scope.chapter_id,10);assert.equal(view.advanced.open,false);assert.ok(view.contextLabel.textContent.includes('第一章'));assert.equal(h.calls.filter(c=>c.url.includes('/questions')).length,0);
 view.count.value='3';view.solutions.checked=true;await view.remember();await plugin.clearKey();assert.equal(plugin.settings.lastSelection.count,3);
 const newView=new h.BankView({app:h.app},plugin);await newView.onOpen();assert.equal(newView.scope.chapter_id,10);assert.equal(newView.count.value,'3');assert.equal(newView.solutions.checked,true);assert.equal(newView.advanced.open,false);
 const knowledge={path:'知识库/一次函数.md',extension:'md'};h.frontmatter.set(knowledge.path,{'知识节点编号':'1489','学科编号':2,'学段编号':2,'精确知识编号':20183});const c=plugin.contextFor(knowledge);await newView.applyContext(c);assert.equal(newView.mode,'knowledge');assert.equal(newView.scope.knowledge_tree_id,1489);assert.equal(newView.scope.edition_id,undefined);assert.ok(newView.contextHint.textContent.includes('未限定教材'));
 let action;h.events.get('file-menu')({addItem:fn=>{const item={setTitle:t=>{action=t;return item;},setIcon:()=>item,onClick:()=>item};fn(item);}},knowledge);assert.equal(action,'从此知识点获取题目');assert.equal(h.calls.filter(c=>c.url.includes('/questions')).length,0);
 const ordinary={path:'普通笔记.md',extension:'md'};assert.equal(plugin.contextFor(ordinary),null);h.dom.window.close();
});
test('知识点取题不会夹带旧教材和章节，保存后有知识树快照',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();await view.applyContext({mode:'knowledge',scope:{subject_id:2,phase_id:2,knowledge_tree_id:1489}});await plugin.setKey('own-fixture',false);
 view.count.value='1';const p=view.run(()=>view.fetch());for(let i=0;i<10&&!h.doc.querySelector('.test-modal');i++)await Promise.resolve();const modal=h.doc.querySelector('.test-modal');[...modal.querySelectorAll('button')].find(b=>b.textContent==='确认获取并扣减额度').click();await p;await view.run(()=>view.saveBatch());
 const url=new URL(h.calls.find(c=>c.url.includes('/questions')).url);assert.equal(url.searchParams.get('knowledge_tree_id'),'1489');assert.equal(url.searchParams.has('edition_id'),false);assert.equal(url.searchParams.has('chapter_id'),false);
 assert.ok(h.files.get('.bank/taxonomy/2-2.json').includes('tizhuang.taxonomy/v1'));const note=[...h.files].find(([k])=>k.startsWith('题目库/')&&k.endsWith('.md'))[1];assert.ok(note.includes('知识节点编号:'));assert.ok(note.includes('教材版本编号: null'));h.dom.window.close();
});
test('取题 HTTP 500 明确显示状态并核对额度，收费请求只发一次',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();await view.applyContext({mode:'chapter',scope:{subject_id:2,phase_id:2,edition_id:59,chapter_id:10,grade_id:201}});await plugin.setKey('own-fixture',false);
 const original=plugin.api.transport;let requests=0;plugin.api.transport=async p=>{if(p.url.includes('/questions')){requests++;return{status:500,json:{detail:'Internal Server Error'}};}return original(p);};
 view.count.value='1';const p=view.run(()=>view.fetch());for(let i=0;i<10&&!h.doc.querySelector('.test-modal');i++)await Promise.resolve();const modal=h.doc.querySelector('.test-modal');[...modal.querySelectorAll('button')].find(b=>b.textContent==='确认获取并扣减额度').click();await p;
 assert.equal(requests,1);assert.match(view.status.textContent,/HTTP 500/);assert.match(view.status.textContent,/0 → 0/);assert.match(view.quota.textContent,/剩余 10 题/);assert.match(view.quota.getAttribute('aria-label'),/剩余题目额度：10/);assert.equal(view.batch,null);h.dom.window.close();
});
test('加载目录时仍可切换版本，迟到的旧目录不能覆盖新选择',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();choose(h,view,'subject_id',2);choose(h,view,'phase_id',2);await settled(view);choose(h,view,'edition_id',59);await settled(view);
 const original=plugin.api.transport;let late;plugin.api.transport=p=>p.url.includes('/chapters')&&p.url.includes('edition_id=142')?new Promise(resolve=>{late=resolve;}):original(p);
 choose(h,view,'edition_id',142);for(let i=0;i<100&&!late;i++)await new Promise(r=>setTimeout(r,1));assert.ok(late);assert.equal(view.loading,true);assert.equal(view.inputs.edition_id.disabled,false);assert.equal(view.inputs.grade_id.disabled,false);assert.equal(view.fetchButton.disabled,true);
 choose(h,view,'edition_id',59);await settled(view);assert.equal(view.scope.edition_id,59);assert.equal(view.nodes[0].edition_id,59);
 late({status:200,json:[{id:21,name:'迟到的其他版本',parent_id:0,subject_id:2,phase_id:2,edition_id:142,grade_id:201}]});await new Promise(r=>setTimeout(r,10));assert.equal(view.scope.edition_id,59);assert.equal(view.nodes[0].edition_id,59);assert.equal(view.loading,false);h.dom.window.close();
});
test('目录超时会提示并恢复操作；切换学期不请求网络，刷新目录为折叠的次要操作',async()=>{
 const h=harness(),plugin=new h.default();await plugin.onload();const view=new h.BankView({app:h.app},plugin);await view.onOpen();choose(h,view,'subject_id',2);choose(h,view,'phase_id',2);await settled(view);choose(h,view,'edition_id',59);await settled(view);
 const before=h.calls.length;choose(h,view,'grade_id',201);await settled(view);assert.equal(h.calls.length,before);assert.equal(view.inputs.grade_id.disabled,false);assert.equal(view.inputs.chapter_id.options.length,2);
 assert.ok(view.fetchButton.classList.contains('tz-primary'));const refresh=[...view.contentEl.querySelectorAll('button')].find(b=>b.textContent==='重新加载目录');assert.ok(refresh.classList.contains('tz-quiet'));assert.equal(refresh.closest('.tz-directory-tools').open,false);
 const original=plugin.api.transport;plugin.api.timeouts.metadata=15;plugin.api.transport=p=>p.url.includes('/chapters')&&p.url.includes('edition_id=142')?new Promise(()=>{}):original(p);
 choose(h,view,'edition_id',142);await settled(view);assert.equal(view.loading,false);assert.match(view.status.textContent,/超过.*秒/);assert.equal(view.inputs.edition_id.disabled,false);assert.equal(view.fetchButton.disabled,false);
 choose(h,view,'edition_id',59);await settled(view);assert.equal(view.nodes[0].edition_id,59);h.dom.window.close();
});
