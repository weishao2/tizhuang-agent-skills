const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../assets/web/library.js'),'utf8');
function setup(connected=false){
 const els={'#pdf-subject':{value:'2'},'#pdf-phase':{value:'3'}};
 const ctx=vm.createContext({state:{connected,catalogs:[{id:'high',subject_id:2,phase_id:3}]},savedDirectoryId:'high',scope:{subject_id:2,phase_id:2},$:s=>els[s],localScopeLists:()=>({subjects:[],phases:[]}),option:(r,v)=>`value:${v}`,hydrateScope:()=>{ctx.requests++},requests:0});
 vm.runInContext(src.slice(src.indexOf('let pdfDirectoryChoice='),src.indexOf('function renderPDF()')),ctx);
 return {ctx,els};
}
test('PDF uses saved scope without selecting textbook or knowledge nodes',()=>{
 const {ctx}=setup();const html=vm.runInContext('pdfScopeFields()',ctx);
 assert.match(html,/value:3/);assert.match(html,/pdf-subject/);assert.doesNotMatch(html,/pdf-directory|edition_id|chapter_id/);
 vm.runInContext('bindPDFScope()',ctx);assert.equal(ctx.requests,0);
});
test('PDF user choice survives rerender instead of reverting to saved high school directory',()=>{
 const {ctx,els}=setup();vm.runInContext('bindPDFScope()',ctx);
 els['#pdf-phase'].value='2';els['#pdf-phase'].onchange();
 assert.equal(vm.runInContext('pdfScopeSelection.phase_id',ctx),'2');
 assert.doesNotMatch(vm.runInContext('pdfScopeFields()',ctx),/value:3/);
});
test('connected PDF refreshes basic lists without downloading a directory',()=>{
 const {ctx}=setup(true);vm.runInContext('bindPDFScope()',ctx);assert.equal(ctx.requests,1);
});
