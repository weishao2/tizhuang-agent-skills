import test from 'node:test';
import assert from 'node:assert/strict';
import {Api} from '../src/core.js';
import {harness} from './ui-harness.mjs';

test('本地与网站页共用固定顺序导航，点击在当前面板路由',async()=>{
 const h=harness(),p=new h.default();await p.onload();await p.store.init();
 const leaf={app:h.app},v=new h.LibraryView(leaf,p);await v.onOpen();
 const expected=['home','website','questions','basket','pdf'];
 for(const tab of ['home','questions','basket','pdf']){await v.show(tab);assert.deepEqual([...v.contentEl.querySelectorAll('.tz-lib-tabs button')].map(b=>b.dataset.tab),expected);assert.equal(v.contentEl.querySelector('[aria-current=page]').dataset.tab,tab);}
 let opened;p.open=async source=>{opened=source;};await v.contentEl.querySelector('[data-tab=website]').onclick();assert.equal(opened,leaf);
 const website=new h.BankView(leaf,p);await website.onOpen();assert.deepEqual([...website.contentEl.querySelectorAll('.tz-lib-tabs button')].map(b=>b.dataset.tab),expected);assert.equal(website.contentEl.querySelector('[aria-current=page]').dataset.tab,'website');
 let local;p.openLibrary=async(tab,source)=>{local={tab,source};};await website.contentEl.querySelector('[data-tab=questions]').onclick();assert.equal(local.source,leaf);assert.equal(local.tab,'questions');h.dom.window.close();
});

test('自动分类按钮运行本地任务并把未确定题交给 Agent，无网站调用',async()=>{
 const h=harness(),p=new h.default();await p.onload();await p.store.init();h.app.vault.adapter.getBasePath=()=>'/vault';
 const v=new h.LibraryView({app:h.app},p);await v.onOpen();await v.show('questions');let command;
 p.runLocal=async(name,args)=>{command={name,args};return {considered:3,classified:2,pending:1,report:'/vault/待整理/分类.md'};};
 await [...v.contentEl.querySelectorAll('button')].find(b=>b.textContent==='自动分类').onclick();const modal=h.doc.querySelector('.test-modal');
 await [...modal.querySelectorAll('button')].find(b=>b.textContent==='分类所有未关联题目').onclick();assert.equal(command.name,'auto-classify');assert.deepEqual([...command.args],[]);assert.match(modal.textContent,/已关联 2 题，1 题待 Agent/);assert.match(modal.querySelector('textarea').value,/暂不分教材章节/);assert.equal(h.calls.length,0);h.dom.window.close();
});

test('试卷相对 HTML 链接走真实文件，不再创建同名空笔记',async()=>{
 const h=harness(),p=new h.default();await p.onload();h.app.vault.adapter.getBasePath=()=>'/vault';let output;p.openLocalOutput=async path=>{output=path;};
 const el=h.doc.createElement('div');el.innerHTML='<a href="打印稿/试卷.html">打印</a><a href="../../outside.html">外部</a>';p.postprocessor(el,{sourcePath:'试卷/demo/试卷.md'});const event=new h.dom.window.MouseEvent('click',{bubbles:true,cancelable:true});el.firstChild.dispatchEvent(event);assert.equal(event.defaultPrevented,true);assert.equal(output,'/vault/试卷/demo/打印稿/试卷.html');assert.equal(h.app.opened,undefined);h.dom.window.close();
});

test('目录额度服务上线后用自己的 Key；额度不足不回退公开接口',async()=>{
 const calls=[];let deny=false,key='own-key';const api=new Api(async req=>{calls.push(req);if(req.url.endsWith('/capabilities'))return {status:200,json:{directory_quota:true}};return deny?{status:403,json:{detail:{code:'directory_scope_limit'}}}:{status:200,json:[{id:1,name:'函数'}]};},()=>key,{scopedDirectories:true});
 await api.meta('knowledge-points',{subject_id:2,phase_id:2});assert.ok(calls[1].url.includes('/local-bank/meta/'));assert.equal(calls[1].headers['X-API-Key'],'own-key');deny=true;
 await assert.rejects(api.meta('knowledge-points',{subject_id:3,phase_id:2}),/目录范围额度已用完/);assert.equal(calls.filter(r=>r.url.includes('/api/v1/meta/')).length,0);
 key='';await assert.rejects(api.meta('chapters',{subject_id:2,phase_id:2,edition_id:59}),/自己的题庄/);
});

test('仅后台尚未发布时使用旧目录，网络失败与权限错误不会降级',async()=>{
 const calls=[];const api=new Api(async r=>{calls.push(r.url);return r.url.endsWith('/capabilities')?{status:404,json:{}}:{status:200,json:[]};},()=>'',{scopedDirectories:true});await api.meta('knowledge-points',{subject_id:2,phase_id:2});assert.equal(api.directoryPolicy,'legacy');assert.ok(calls[1].includes('/api/v1/meta/knowledge-points'));
 const down=new Api(async()=>{throw Error('offline');},()=>'',{scopedDirectories:true});await assert.rejects(down.meta('knowledge-points',{subject_id:2,phase_id:2}),/网络连接/);assert.equal(down.directoryPolicy,'unknown');
});
