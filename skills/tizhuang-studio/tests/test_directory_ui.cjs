const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../assets/web/library.js'),'utf8');
const code=source.split('const originalSetTab=')[0]+source.slice(source.indexOf('function matchSavedScope(){'),source.indexOf('renderFind=function(){'))+source.slice(source.indexOf('function directoryPickerModel(rows){'),source.indexOf('function openDirectoryPicker('));
const trees=[
  {id:'knowledge-2-2',kind:'knowledge',subject_id:2,phase_id:2,nodes:[{id:10,name:'函数'}]},
  {id:'chapter-2-2-4',kind:'chapter',subject_id:2,phase_id:2,edition_id:4,nodes:[{id:20,name:'第一章'}]},
];
function setup(pref,workspace='one'){
  const store=new Map(pref?[['tizhuang:directory:one',JSON.stringify(pref)]]:[]);
  const ctx=vm.createContext({state:{workspace,catalogs:trees},scope:{grade_id:'old',knowledge_tree_id:'old'},nodes:[],chapters:[],fetchOffset:10,filterMode:'knowledge',localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)}});
  vm.runInContext(code,ctx);
  return {ctx,store,run:s=>JSON.parse(JSON.stringify(vm.runInContext(s,ctx)))};
}
test('first visit reuses a downloaded tree without fetching remote metadata',()=>{
  const t=setup();t.run('initializeDirectoryPreference();scope');
  assert.deepEqual(t.run('scope'),{subject_id:'2',phase_id:'2'});
  assert.equal(t.run('nodes.length'),1);
});
test('remembered chapter replaces stale knowledge and grade filters',()=>{
  const t=setup({id:trees[1].id});
  assert.deepEqual(t.run('initializeDirectoryPreference();scope'),{subject_id:'2',phase_id:'2',edition_id:'4'});
  assert.equal(t.run('filterMode'),'chapter');assert.equal(t.run('nodes.length'),0);
  assert.equal(t.run('chapters[0].id'),20);
});
test('explicit clear remains clear on reload and does not affect another workspace',()=>{
  const t=setup({cleared:true});t.run('initializeDirectoryPreference();scope');
  assert.equal(t.run('savedDirectoryId'),'');
  const other=setup({cleared:true},'two');other.run('initializeDirectoryPreference();scope');
  assert.equal(other.run('savedDirectoryId'),trees[0].id);
});
test('library node is carried into search only when present in that catalog',()=>{
  const t=setup();
  assert.equal(t.run('useSavedDirectory(state.catalogs[0],10);scope.knowledge_tree_id'),'10');
  assert.deepEqual(t.run('useSavedDirectory(state.catalogs[1],10);scope'),{subject_id:'2',phase_id:'2',edition_id:'4'});
  assert.equal(t.run('fetchOffset'),0);
});
test('changing subject cannot reuse another subjects knowledge tree',()=>{
  const t=setup();t.run('initializeDirectoryPreference();scope');
  assert.equal(t.run("scope.subject_id='3';matchSavedScope();savedDirectoryId"),'');
  assert.equal(t.run('nodes.length'),0);assert.equal(t.run('chapters.length'),0);
});
test('chapter mode reuses only the chosen editions saved directory',()=>{
  const t=setup();
  assert.equal(t.run("scope={subject_id:'2',phase_id:'2',edition_id:'4'};filterMode='chapter';matchSavedScope().id"),trees[1].id);
  assert.equal(t.run("scope.edition_id='5';matchSavedScope();savedDirectoryId"),'');
  assert.equal(t.run('chapters.length'),0);
});
test('tree search distinguishes duplicate names by full path and accepts numeric IDs',()=>{
  const t=setup();t.ctx.pickerRows=[{id:1,name:'函数'},{id:2,parent_id:1,name:'性质'},{id:3,name:'几何'},{id:4,parent_id:3,name:'性质'}];
  assert.deepEqual(t.run("directoryPickerModel(pickerRows).search('函数 性质').map(n=>n.id)"),['2']);
  assert.equal(t.run('directoryPickerModel(pickerRows).path(4)'),'几何 / 性质');
  assert.deepEqual(t.run("directoryPickerModel(pickerRows).children.get('1').map(n=>n.id)"),['2']);
});
test('tree search returns no false result for unmatched text',()=>{
  const t=setup();assert.equal(t.run("directoryPickerModel(state.catalogs[0].nodes).search('三角形').length"),0);
});
test('manual scope and search mode survive refresh without silently selecting a different tree',()=>{
  const t=setup({cleared:true,mode:'chapter',scope:{subject_id:'2',phase_id:'3',edition_id:'9'}});
  assert.deepEqual(t.run('initializeDirectoryPreference();scope'),{subject_id:'2',phase_id:'3',edition_id:'9'});
  assert.equal(t.run('filterMode'),'chapter');assert.equal(t.run('savedDirectoryId'),'');
});
