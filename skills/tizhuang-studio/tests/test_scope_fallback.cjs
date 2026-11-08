const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../assets/web/library.js'),'utf8');
const code=source.slice(source.indexOf('function localScopeLists('),source.indexOf('function knowledgeLabels'));
function context(api){
 const elements={'#pdf-subject':{value:'2'},'#pdf-phase':{value:'3'},'#pdf-scope-note':{textContent:''}};
 const ctx=vm.createContext({catalog:{},state:{catalogs:[{subject_id:2,phase_id:2},{subject_id:2,phase_id:3}]},scope:{},api,$:s=>elements[s],option:(rows,value)=>JSON.stringify({rows,value})});
 vm.runInContext(code,ctx);return {ctx,elements};
}
test('offline PDF scopes include high school without a key or quota request',async()=>{
 const {ctx,elements}=context(async()=>{throw Error('network');});
 assert.match(vm.runInContext("scopeFields('pdf')",ctx),/高中/);
 await vm.runInContext("hydrateScope('pdf')",ctx);
 assert.match(elements['#pdf-scope-note'].textContent,/不代表目录未开通/);
 assert.equal(elements['#pdf-phase'].value,'3');
});
test('partial refresh preserves high school choice and updates successful list',async()=>{
 const {ctx,elements}=context(async name=>{if(name.endsWith('subjects'))return [{id:2,name:'数学'},{id:8,name:'物理'}];throw Error('network');});
 await vm.runInContext("hydrateScope('pdf')",ctx);
 assert.match(elements['#pdf-subject'].innerHTML,/物理/);
 assert.equal(elements['#pdf-phase'].value,'3');
});
test('late metadata response does not replace a newly rendered form',async()=>{
 let finish;const pending=new Promise(r=>finish=r);
 const {ctx,elements}=context(()=>pending);
 const hydration=vm.runInContext("hydrateScope('pdf')",ctx);
 elements['#pdf-subject']={value:'8',innerHTML:'new form'};
 finish([{id:2,name:'数学'}]);await hydration;
 assert.equal(elements['#pdf-subject'].innerHTML,'new form');
});
