import test from 'node:test';
import assert from 'node:assert/strict';
import {harness} from './ui-harness.mjs';

test('PDF 准备不再自动导入整题截图，指令要求可编辑正文和去掉原题号',async()=>{
 const h=harness(),p=new h.default();await p.onload();await p.store.init();
 h.app.vault.adapter.getBasePath=()=>'/test-vault';p.store.io.writeBinary=async(path,bytes)=>h.files.set(path,bytes);
 const calls=[];p.runLocal=async(command,args)=>{calls.push(command);return {batch:'a'.repeat(24),status:'prepared',imported:0,report:'待整理/测试报告.md'};};
 const view=new h.LibraryView({app:h.app},p);await view.onOpen();await view.show('pdf');
 const file=view.contentEl.querySelector('input[type=file]');Object.defineProperty(file,'files',{value:[{name:'试卷.pdf',size:100,arrayBuffer:async()=>new TextEncoder().encode('%PDF-test').buffer}]});
 await [...view.contentEl.querySelectorAll('button')].find(b=>b.textContent==='准备导入').onclick();
 assert.deepEqual(calls,['pdf-prepare']);
 const prompt=view.contentEl.querySelector('textarea').value;
 for(const text of ['可编辑 Markdown/LaTeX','单独提取配图','去掉正文原题号','来源记录','图①','v2','本地标准知识点树','未指定教材不补章节'])assert.ok(prompt.includes(text),text);
 assert.equal(h.calls.length,0);await view.onClose();h.dom.window.close();
});

test('只有部分导入的可编辑批次可直接继续，旧区域候选交给 Agent',async()=>{
 const h=harness(),p=new h.default();await p.onload();await p.store.init();h.app.vault.adapter.getBasePath=()=>'/test-vault';
 const view=new h.LibraryView({app:h.app},p);await view.onOpen();
 for(const [status,representation,expected]of [['prepared',undefined,'复制 Agent 指令'],['partial',undefined,'复制 Agent 指令'],['partial','editable','继续导入']]){
  const parent=h.doc.createElement('div');view.batchRow(parent,{id:'b'.repeat(24),filename:'试卷.pdf',pages:[{}],status,representation,imported:{}});
  assert.equal(parent.querySelector('button').textContent,expected);
 }
 await view.onClose();h.dom.window.close();
});
