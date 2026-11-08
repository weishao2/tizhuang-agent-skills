const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../assets/web/workflow.js'),'utf8').split("let preferencesWorkspace='';")[0];
const ctx=vm.createContext({});vm.runInContext(src,ctx);
const run=s=>JSON.parse(JSON.stringify(vm.runInContext(s,ctx)));
test('parent tags include descendants but not similar prefixes',()=>{
  assert.equal(run("tagMatches(['期中/易错'],'期中')"),true);
  assert.equal(run("tagMatches(['期中/易错'],'期')"),false);
});
test('tag hierarchy deduplicates parent counts and excludes archive',()=>{
  ctx.rows=[{id:'a',tags:['期中/易错','期中/基础']},{id:'b',tags:['期中/易错']},{id:'c',tags:['期中'],archived:true}];
  assert.deepEqual(run("tagHierarchy(rows).map(n=>[n.id,n.ids.size])"),[['期中',2],['期中/基础',1],['期中/易错',2]]);
});
test('onboarding derives progress from real state, never confirms on behalf of teacher',()=>{
  ctx.s={questions:[],catalogs:[],exports:[]};assert.deepEqual(run('startSteps(s).map(x=>x.done)'),[false,false,false,false]);
  ctx.s={questions:[{status:'draft'}],catalogs:[{kind:'knowledge'}],exports:[]};assert.deepEqual(run('startSteps(s).map(x=>x.done)'),[true,true,false,false]);
  ctx.s.questions[0].status='reviewed';ctx.s.exports=[{}];assert.ok(run('startSteps(s).every(x=>x.done)'));
});
test('preferences are bounded, restore filters and reset page',()=>{
  ctx.pref={count:12,library:{tag:'期中',query:'函数',unused:true,status:'draft',page:100}};
  assert.equal(run('cleanPreferences(pref).count'),12);assert.equal(run('cleanPreferences(pref).library.tag'),'期中');
  assert.equal(run('cleanPreferences(pref).library.page'),0);assert.equal(run('cleanPreferences({count:999}).count'),5);
});
test('cursor key ignores count and is shared across numeric/string scope IDs',()=>{
  assert.equal(run('scopeCursorKey({subject_id:2,phase_id:2,count:5})'),run('scopeCursorKey({subject_id:"2",phase_id:"2",count:10})'));
});
test('classification submits only current edition plus knowledge',()=>{
  assert.equal(run("selectionVisible({kind:'chapter',edition_id:4},5)"),false);
  assert.equal(run("selectionVisible({kind:'knowledge'},5)"),true);
});
