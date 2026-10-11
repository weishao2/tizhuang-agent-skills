import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const bundle=await readFile('dist/tizhuang-question-bank/main.js','utf8');
export function harness(){
 const dom=new JSDOM('<html><body></body></html>',{url:'https://test.invalid'}),doc=dom.window.document,calls=[],files=new Map(),secrets=new Map(),notices=[];
 const io={exists:async p=>files.has(p),mkdir:async p=>files.set(p,null),write:async(p,v)=>files.set(p,v),read:async p=>files.get(p),remove:async p=>files.delete(p),list:async p=>({files:[...files.keys()].filter(k=>k.startsWith(p+'/')&&files.get(k)!==null)})};
 const events=new Map(),frontmatter=new Map();const app={vault:{adapter:io,getAbstractFileByPath:path=>({path,extension:'md'})},metadataCache:{getFileCache:f=>({frontmatter:frontmatter.get(f.path)})},secretStorage:{getSecret:id=>secrets.get(id)||null,setSecret:(id,v)=>secrets.set(id,v)},setting:{open(){},openTabById(){}},workspace:{on:(name,fn)=>{events.set(name,fn);return{name};},getLeavesOfType:()=>[],getActiveFile:()=>app.activeFile,openLinkText:async p=>{app.opened=p;}}};
 class Plugin{constructor(){this.app=app;this.manifest={id:'tizhuang-question-bank'};this.saved=null;this.commands=[];}async loadData(){return{};}async saveData(data){this.saved=JSON.stringify(data);}registerView(){}registerEvent(){}addSettingTab(tab){this.tab=tab;}addRibbonIcon(icon,title){this.ribbonTitle=title;}addCommand(command){this.commands.push(command);}registerMarkdownPostProcessor(fn){this.postprocessor=fn;}}
 class ItemView{constructor(leaf){this.leaf=leaf;this.app=leaf.app;this.contentEl=doc.createElement('div');doc.body.append(this.contentEl);}}
 class Modal{constructor(app){this.app=app;this.contentEl=doc.createElement('div');this.contentEl.className='test-modal';}open(){doc.body.append(this.contentEl);this.onOpen();}close(){this.onClose();this.contentEl.remove();}}
 class PluginSettingTab{constructor(app,plugin){this.app=app;this.plugin=plugin;this.containerEl=doc.createElement('div');}}
 class Setting{constructor(el){this.el=doc.createElement('section');el.append(this.el);}setName(t){this.el.append(doc.createTextNode(t));return this;}setDesc(){return this;}addText(fn){const inputEl=doc.createElement('input');this.el.append(inputEl);const api={inputEl,setPlaceholder(t){inputEl.placeholder=t;return api;},onChange(fn){inputEl.addEventListener('input',()=>fn(inputEl.value));return api;}};fn(api);return this;}addToggle(fn){const api={setValue(){return api;},setDisabled(){return api;},onChange(){return api;}};fn(api);return this;}addButton(fn){const el=doc.createElement('button');this.el.append(el);const api={setButtonText(t){el.textContent=t;return api;},setCta(){return api;},onClick(fn){el.addEventListener('click',fn);return api;}};fn(api);return this;}}
 const raw={id:123,subject_id:2,grade_id:200,title_html:'已知 $y=2x+1$，求函数值。<script>steal()</script>',options_html:{},options:{B:'第二项',A:'第一项'},answer_html:'<b>7</b>',subquestions:[]};
 const nodes=[{id:10,name:'第一章',parent_id:0,subject_id:2,phase_id:2,edition_id:59,grade_id:201}];
 const requestUrl=async p=>{calls.push(p);const u=new URL(p.url);let json;switch(u.pathname.split('/').pop()){
 case 'capabilities':return {status:404,json:{detail:'not yet deployed'}};
 case 'subjects':json=[{id:2,name:'数学'}];break;case 'phases':json=[{id:2,name:'初中'}];break;case 'grades':json=[{id:201,name:'七年级上学期'}];break;case 'editions':json=[{id:59,name:'人教新版'},{id:142,name:'人教版2024'}];break;
 case 'knowledge-points':json=[{id:1480,name:'函数',parent_id:0},{id:1489,name:'一次函数',parent_id:1480}];break;case 'chapters':json=nodes.map(n=>({...n,edition_id:Number(u.searchParams.get('edition_id'))}));break;case 'quota':json={remaining:10,used:0};break;case 'questions':json={items:[raw],quota_remaining_today:9};break;default:throw Error('unexpected route');}return{status:200,json};};
 const mocks={Plugin,ItemView,Modal,PluginSettingTab,Setting,Notice:class{constructor(t){notices.push(t);}},requestUrl,MarkdownRenderer:{render:async(app,text,el)=>{el.textContent=text;}}};
 const context=vm.createContext({window:dom.window,document:doc,crypto:webcrypto,structuredClone,TextEncoder,URL,console,setTimeout,clearTimeout,module:{exports:{}},require:name=>{assert.equal(name,'obsidian');return mocks;}});vm.runInContext(bundle,context);
 return{...context.module.exports,app,doc,dom,calls,files,secrets,notices,events,frontmatter,renderer:mocks.MarkdownRenderer};
}
