const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../assets/web/app.js'),'utf8');
const ctx=vm.createContext({});
vm.runInContext(source.slice(source.indexOf('function mathSummary('),source.indexOf('const plain=')),ctx);
const text=s=>({nodeType:3,textContent:s});
const node=(tag,...children)=>({nodeType:1,localName:tag,childNodes:children.map(c=>typeof c==='string'?text(c):c)});
test('fractions remain fractions in summaries, including nested fractions',()=>{
 assert.equal(ctx.mathSummary(node('math',node('mfrac',node('mn','1'),node('mn','6')))),'1/6');
 assert.equal(ctx.mathSummary(node('mfrac',node('mrow','x','+','1'),node('mfrac','2','3'))),'(x+1)/(2/3)');
});
test('powers and roots do not collapse into plain digits',()=>{
 assert.equal(ctx.mathSummary(node('msup','10','5')),'10^(5)');
 assert.equal(ctx.mathSummary(node('msqrt',node('mrow','x','+','1'))),'√(x+1)');
});
test('annotations do not duplicate visible formulas and complex structures are explicit',()=>{
 assert.equal(ctx.mathSummary(node('semantics',node('mrow','x','+','1'),node('annotation','x+1'))),'x+1');
 assert.equal(ctx.mathSummary(node('mtable',node('mtr','1','2'))),'[公式]');
});
