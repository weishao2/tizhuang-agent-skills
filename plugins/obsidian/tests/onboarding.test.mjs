import test from 'node:test';
import assert from 'node:assert/strict';
import {startSteps} from '../src/library-core.js';
import {explainFailure} from '../src/local-runner.js';
import {harness} from './ui-harness.mjs';

const row=status=>({q:{status}});

test('新手引导只看真实本地状态：逐步解锁，当前步骤唯一', () => {
  let plan = startSteps({rows: [], trees: [], papers: []});
  assert.equal(plan.current.id, 'tree');
  assert.equal(plan.steps.find(s => s.id === 'review').locked, true);
  plan = startSteps({rows: [row('draft')], trees: [{kind: 'knowledge'}], papers: []});
  assert.deepEqual(plan.steps.map(s => s.done), [true, true, false, false]);
  assert.equal(plan.current.id, 'review');
  plan = startSteps({rows: [row('reviewed')], trees: [{kind: 'knowledge'}], papers: []});
  assert.equal(plan.current.id, 'paper');
  plan = startSteps({rows: [row('reviewed')], trees: [{kind: 'knowledge'}], papers: ['试卷/a/试卷.md']});
  assert.equal(plan.complete, true);
  assert.equal(plan.current, null);
  // a textbook tree alone is not a knowledge tree
  assert.equal(startSteps({rows: [], trees: [{kind: 'chapter'}], papers: []}).steps[0].done, false);
});

test('本地处理失败给出可执行的一句话，而不是堆栈', () => {
  assert.match(explainFailure({code: 'ENOENT'}), /安装 Python 3\.10/);
  assert.match(explainFailure({}, "ModuleNotFoundError: No module named 'yaml'"), /requirements\.txt/);
  assert.match(explainFailure({killed: true}), /120 秒/);
  assert.match(explainFailure({}, 'boom'), /boom/);
});

test('空题库首页显示引导，空列表给出下一步按钮；完成后引导消失', async () => {
  const h = harness(), p = new h.default();
  await p.onload();
  await p.store.init();
  const view = new h.LibraryView({app: h.app}, p);
  await view.onOpen();
  const card = view.contentEl.querySelector('.tz-start');
  assert.ok(card, '空题库应显示引导');
  assert.equal(card.querySelectorAll('.tz-start-step').length, 4);
  assert.equal(card.querySelectorAll('.is-current').length, 1);
  assert.equal(view.contentEl.querySelector('.tz-status').getAttribute('role'), 'status');
  await view.show('questions', {});
  const empty = view.contentEl.querySelector('.tz-local-empty');
  assert.match(empty.textContent, /题库还是空的/);
  assert.ok([...empty.querySelectorAll('button')].some(b => b.textContent === '导入 PDF'));
  h.dom.window.close();
});

// ---- 第一步闭环：下载知识树必须落盘，首页才会前进 ----
import {noteText} from '../src/core.js';
const sample=(id,scope={})=>({schema:'tizhuang.question/v1',id,title:'一道数学题',content:'原题 $x=2$。',answer:'7',analysis:'解析',tags:[],status:'draft',type:'选择题',score:5,subject_id:2,phase_id:2,edition_id:142,chapter_ids:[],knowledge_tree_ids:[],knowledge_ids:[],source:{kind:'local'},...scope});
const tick=()=>new Promise(r=>setTimeout(r,5));

test('选好学科学段后知识树保存到本地，回到首页第一步变为已完成', async () => {
  const h = harness(), p = new h.default();
  await p.onload();
  const bank = new h.BankView({app: h.app}, p);
  await bank.onOpen();
  await bank.applyContext({mode: 'chapter', scope: {subject_id: 2, phase_id: 2, edition_id: 59, chapter_id: 10}});
  const saved = h.files.get('.bank/taxonomy/2-2.json');
  assert.ok(saved, '知识树应写入 .bank/taxonomy/2-2.json');
  const data = JSON.parse(saved);
  assert.equal(data.subject_id, 2);
  assert.equal(data.phase_id, 2);
  assert.ok(data.nodes.length > 0);
  const mapping=JSON.parse(h.files.get('.bank/ui-paths.json'));
  const notePath=mapping.knowledge['2-2']['1489'];
  assert.match(notePath,/资料\/知识目录\/初中 · 数学/);
  assert.match(h.files.get(notePath),/知识节点编号:.*1489/);
  assert.ok(h.files.has('资料/知识目录/初中 · 数学/知识树.md'));
  assert.ok(h.files.has('资料/教材目录/初中 · 数学 · 人教新版/教材目录.md'));
  await p.openDirectory(bank,'chapter');
  assert.equal(h.app.opened,JSON.parse(h.files.get('.bank/ui-paths.json')).chapters['2-2-59']['10']);
  await p.openDirectory(bank,'knowledge');
  assert.equal(h.app.opened,'资料/知识目录/初中 · 数学/知识树.md');
  // 已有快照属于老师，再次加载不覆盖
  h.files.set('.bank/taxonomy/2-2.json', JSON.stringify({...data, marker: 'keep'}));
  await bank.loadKnowledge(false, true);
  assert.equal(JSON.parse(h.files.get('.bank/taxonomy/2-2.json')).marker, 'keep');
  // 首页：不用手动刷新，show('home') 会重读本地状态
  const lib = new h.LibraryView({app: h.app}, p);
  await lib.onOpen();
  await lib.show('home');
  assert.equal(lib.contentEl.querySelector('.tz-start-step').classList.contains('is-done'), true);
  h.dom.window.close();
});

test('目录写入失败可以重试，不能把失败记录为已生成',async()=>{
  const h=harness(),p=new h.default();await p.onload();await p.store.init();
  const write=p.store.io.write;let failed=false;
  p.store.io.write=async(path,text)=>{if(path.endsWith('知识树.md')&&!failed){failed=true;throw Error('disk full');}return write(path,text);};
  const nodes=[{id:1,name:'函数',parent_id:0}];
  await assert.rejects(p.store.saveTaxonomy(2,2,nodes),/disk full/);
  assert.equal(p.store.materializedTrees.size,0);
  await p.store.saveTaxonomy(2,2,nodes);
  assert.ok([...h.files.keys()].some(path=>path.endsWith('知识树.md')));
  assert.equal([...h.files.keys()].filter(path=>path.endsWith('/函数.md')).length,1);
  h.dom.window.close();
});

test('旧快照没有可见目录时首页离线补齐；保留题目、快照和老师笔记，重复进入不重复写',async()=>{
  const h=harness(),p=new h.default();await p.onload();await p.store.init();
  const data={schema:'tizhuang.taxonomy/v1',subject_id:2,phase_id:2,nodes:[{id:1,name:'数与式',parent_id:0},{id:2,name:'乘方',parent_id:1},{id:3,name:'乘方',parent_id:1}]};
  const snapshot=JSON.stringify(data);h.files.set('.bank/taxonomy/2-2.json',snapshot);
  h.files.set('.bank/catalog/names.json',JSON.stringify({subjects:{2:'数学'},phases:{2:'初中'}}));
  const original=noteText(sample('q1'));h.files.set('题目库/原题.md',original);
  const lib=new h.LibraryView({app:h.app},p);await lib.onOpen();
  const paths=JSON.parse(h.files.get('.bank/ui-paths.json')).knowledge['2-2'];
  assert.notEqual(paths['2'],paths['3']);assert.ok(h.files.get(paths['2']).includes('父知识点：'));
  h.files.set(paths['2'],h.files.get(paths['2'])+'\n老师补充：保留我');
  const before=new Map(h.files);p.store.materializedTrees.clear();await lib.refresh();
  assert.deepEqual(h.files,before);assert.equal(h.files.get('.bank/taxonomy/2-2.json'),snapshot);
  assert.equal(h.files.get('题目库/原题.md'),original);assert.equal(h.calls.length,0);
  h.dom.window.close();
});

// ---- 第三步闭环：列表里就能确认核对，并走经过校验的 CLI ----
test('待核对题目可在列表中确认；取消不写入，确认才调用 review', async () => {
  const h = harness(), p = new h.default();
  await p.onload();
  await p.store.init();
  h.files.set('题目库/题1.md', noteText(sample('q1')));
  const calls = [];
  p.runLocal = async (command, args) => { calls.push([command, args]); h.files.set('题目库/题1.md', noteText(sample('q1', {status: 'reviewed'}))); return [{id: 'q1', status: 'reviewed'}]; };
  const lib = new h.LibraryView({app: h.app}, p);
  await lib.onOpen();
  await lib.show('questions', {});
  const button = [...lib.contentEl.querySelectorAll('button')].find(b => b.textContent === '标记为已核对');
  assert.ok(button, '待核对题目应有“标记为已核对”');
  button.click();
  await tick();
  assert.equal(calls.length, 0, '点击后需要二次确认，不能直接写入');
  const modal = h.doc.querySelector('.test-modal');
  assert.match(modal.textContent, /逐题看过/);
  [...modal.querySelectorAll('button')].find(b => b.textContent === '取消').click();
  await tick();
  assert.equal(calls.length, 0);
  button.click();
  await tick();
  [...h.doc.querySelector('.test-modal').querySelectorAll('button')].find(b => b.textContent === '我已核对，标记').click();
  await tick(); await tick();
  assert.equal(JSON.stringify(calls), JSON.stringify([['review', ['--ids', 'q1', '--confirm']]])); // 跨 vm 域，比较序列化结果
  assert.ok(![...lib.contentEl.querySelectorAll('button')].some(b => b.textContent === '标记为已核对'));
  assert.match(lib.contentEl.textContent, /已核对/);
  h.dom.window.close();
});

// ---- 一键环境检查 ----
import {checkEnvironment, pythonCandidates, describeEnvironment} from '../src/local-runner.js';
const fakePlugin = (pythonPath = '') => ({settings: {pythonPath}, manifest: {dir: '.obsidian/plugins/x'}, app: {vault: {adapter: {getBasePath: () => '/vault'}}}});
const doctor = (ok, extra = {}) => ({error: ok ? null : Object.assign(Error('x'), {code: 1}), stdout: JSON.stringify({ok, python: '/py/bin/python', checks: ok ? [{name: 'Python 3.10+', ok: true}] : [{name: '运行依赖', ok: false, detail: '缺少：PyYAML', fix: '/py/bin/python -m pip install -r "req.txt"'}], ...extra})});

test('Python 候选：用户指定则只试指定的；Windows 兜底 py -3', () => {
  assert.deepEqual(pythonCandidates(' C:\\Py\\python.exe ', 'win32').map(c => c.file), ['C:\\Py\\python.exe']);
  assert.deepEqual(pythonCandidates('', 'win32').map(c => [c.file, ...c.prefix].join(' ')), ['python', 'py -3']);
  assert.deepEqual(pythonCandidates('', 'linux').map(c => c.file), ['python3', 'python']);
});

test('环境检查：一个 Python 失败会继续试下一个，成功即停；缺依赖给出可复制的修复命令', async () => {
  const win = fakePlugin(); // 默认候选按当前平台，这里直接注入 exec 观察调用顺序
  const order = [];
  const missing = Object.assign(Error('nf'), {code: 'ENOENT'});
  let r = await checkEnvironment(win, async file => { order.push(file); return order.length === 1 ? {error: missing, stdout: ''} : doctor(true); });
  assert.equal(r.ok, true);
  assert.equal(order.length, 2);
  assert.match(r.summary, /环境正常/);
  r = await checkEnvironment(fakePlugin('/py/bin/python'), async () => doctor(false));
  assert.equal(r.ok, false);
  assert.match(r.summary, /缺少：PyYAML/);
  assert.match(r.fix, /pip install/);
  r = await checkEnvironment(fakePlugin(), async () => ({error: missing, stdout: ''}));
  assert.equal(r.ok, false);
  assert.match(r.summary, /没有找到 Python/);
  assert.equal(r.fix, '');
  assert.match(describeEnvironment([]), /没有找到 Python/);
});

// ---- 第二轮评审：区分未安装/超时/脚本异常；批量核对只作用于屏幕上显示的题 ----
test('环境检查区分未安装、超时和脚本异常，建议各不相同', async () => {
  const p = fakePlugin('/py/python');
  let r = await checkEnvironment(p, async () => ({error: Object.assign(Error('t'), {killed: true, signal: 'SIGTERM'}), stdout: ''}));
  assert.equal(r.tried[0].state, 'timeout');
  assert.match(r.summary, /已安装.*超过 30 秒.*不需要重新安装/);
  r = await checkEnvironment(p, async () => ({error: Object.assign(Error('boom'), {code: 1}), stdout: '', stderr: 'SyntaxError: bad'}));
  assert.equal(r.tried[0].state, 'broken');
  assert.match(r.summary, /检查脚本没有正常运行.*SyntaxError.*不需要重装 Python/);
  r = await checkEnvironment(p, async () => ({error: Object.assign(Error('nf'), {code: 'ENOENT'}), stdout: ''}));
  assert.equal(r.tried[0].state, 'missing');
  assert.match(r.summary, /没有找到 Python/);
});

test('超过 100 题时批量核对只针对显示的题，屏幕上全是已核对时不出现该按钮', async () => {
  const h = harness(), p = new h.default();
  await p.onload();
  await p.store.init();
  const id = n => 'q' + String(n).padStart(3, '0');
  for (let n = 1; n <= 110; n++) h.files.set(`题目库/${id(n)}.md`, noteText(sample(id(n), {status: n <= 100 ? 'reviewed' : 'draft'})));
  const lib = new h.LibraryView({app: h.app}, p);
  await lib.onOpen();
  await lib.show('questions', {});
  assert.equal(lib.contentEl.querySelectorAll('.tz-local-card').length, 100);
  assert.ok(![...lib.contentEl.querySelectorAll('button')].some(b => b.textContent.startsWith('核对本页显示的待核对题')), '前 100 题都已核对，不应出现批量核对按钮');
  // 把一道显示中的题改回待核对：按钮只含这一题，不含屏幕外的 10 题
  h.files.set('题目库/q005.md', noteText(sample('q005', {status: 'draft'})));
  await lib.refresh();
  await lib.show('questions', {});
  const calls = [];
  p.runLocal = async (command, args) => { calls.push(args); return []; };
  const batch = [...lib.contentEl.querySelectorAll('button')].find(b => b.textContent.startsWith('核对本页显示的待核对题'));
  assert.match(batch.textContent, /（1）/);
  batch.click();
  await tick();
  [...h.doc.querySelector('.test-modal').querySelectorAll('button')].find(b => b.textContent === '我已核对，标记').click();
  await tick(); await tick();
  assert.equal(JSON.stringify(calls), JSON.stringify([['--ids', 'q005', '--confirm']]));
  h.dom.window.close();
});
