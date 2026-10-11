import {renderNavigation} from './navigation.js';
import {openDirectory} from './directory-navigation.js';
import {renderBrand} from './brand.js';
import {PaperBasket} from './paper-basket.js';
import {Plugin, ItemView, PluginSettingTab, Setting, Modal, Notice, requestUrl, MarkdownRenderer} from 'obsidian';
import DOMPurify from 'dompurify';
import TurndownService from 'turndown';
import {Api, Store, BASE, validateChapters, validateKnowledge, requireScope, questionFrom, localize, redacted, contextFromProperties, cursorKey, directoryNodes, queryFilters} from './core.js';
import {MetadataCache} from './metadata-cache.js';
import {LibraryView,LIBRARY_VIEW} from './library-view.js';
import {runLocal} from './local-runner.js';
const VIEW='tizhuang-teacher-bank';
const td=new TurndownService({headingStyle:'atx',codeBlockStyle:'fenced'});
// Preserve mathematical markup; flattening a table/math expression would change the question.
td.keep(['table','math','sup','sub']);
export const markdown=value=>{
  const math=[];const prefix='TZMATH'+crypto.randomUUID().replaceAll('-','')+'TOKEN';
  const safe=DOMPurify.sanitize(String(value),{USE_PROFILES:{html:true,mathMl:true},FORBID_TAGS:['script','style','iframe','object','embed','form','input','button'],FORBID_ATTR:['style','srcset']});
  // Turndown escapes backslashes/underscores in ordinary text. Shield TeX delimiters first.
  const shielded=safe.replace(/\$\$[\s\S]*?\$\$|\$(?:\\.|[^$])*?\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]/g,source=>{
    if(source.includes('<'))return source;
    const decoder=document.createElement('textarea');decoder.innerHTML=source;let text=decoder.value;
    if(text.startsWith('\\('))text='$'+text.slice(2,-2)+'$';if(text.startsWith('\\['))text='$$'+text.slice(2,-2)+'$$';
    const token=prefix+math.length+'END';math.push({token,text});return token;
  });
  let result=td.turndown(shielded);for(const {token,text}of math)result=result.replaceAll(token,text);return result;
};
const node=(parent,tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;parent.append(e);return e;};
const button=(parent,text,run,kind='secondary')=>{const b=node(parent,'button',text,'tz-'+kind+(kind==='primary'?' mod-cta':''));b.type='button';b.addEventListener('click',run);return b;};
const label=(parent,text)=>node(parent,'label',text,'tz-label');
const iconButton=(parent,title,run,icon)=>{const b=button(parent,'',run,'quiet');b.classList.add('tz-icon-button');b.title=title;b.setAttribute('aria-label',title);const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',icon);svg.append(path);b.append(svg);return b;};
const icons={website:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18',key:'M7 10a5 5 0 1 0 0 10 5 5 0 0 0 0-10M10.5 11.5 21 1M18 4l3 3M15 7l3 3',refresh:'M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 3M5 15a8 8 0 0 0 13 3',node:'M4 4h16v16H4zM8 9h8M8 13h5',clear:'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5m4-5v5',open:'M14 4h6v6M20 4 10 14M10 4H4v16h16v-6'};
class SpendModal extends Modal{
  constructor(app,summary,resolve){super(app);this.summary=summary;this.resolve=resolve;this.accepted=false;}
  onOpen(){node(this.contentEl,'h2','确认获取题目');node(this.contentEl,'p',this.summary);node(this.contentEl,'p','按网站实际返回的题数扣减今日额度。再次获取也会扣额，本地重复题不会退额。');const actions=node(this.contentEl,'div',null,'tz-actions');button(actions,'取消',()=>this.close());button(actions,'确认获取并扣减额度',()=>{this.accepted=true;this.close();},'primary');}
  onClose(){this.resolve(this.accepted);this.contentEl.replaceChildren();}
}
class CredentialsTab extends PluginSettingTab{
  constructor(app,plugin){super(app,plugin);this.plugin=plugin;}
  display(){
    const {containerEl}=this;containerEl.replaceChildren();node(containerEl,'h2','题庄本地题库设置');
    node(containerEl,'p','使用自己的题庄 API Key，题目从自己的今日额度扣减。请在此输入，不要发送到聊天中。');
    let value='';new Setting(containerEl).setName('题庄 API Key').setDesc('输入后点击下方保存。本地题库 skill 和现有取题 skill 的凭证不会自动读取。').addText(t=>{t.inputEl.type='password';t.inputEl.autocomplete='off';t.setPlaceholder('输入自己的 API Key').onChange(v=>{value=v;});});
    let persist=Boolean(this.app.secretStorage);new Setting(containerEl).setName('保存到 Obsidian 密钥存储').setDesc(this.app.secretStorage?'只保存密钥引用到插件配置，不把 API Key 写入笔记或插件配置。':'当前 Obsidian 版本不支持密钥存储，仅在本次应用运行期间使用。').addToggle(t=>t.setValue(persist).setDisabled(!this.app.secretStorage).onChange(v=>{persist=v;}));
    new Setting(containerEl).setName('应用凭证').addButton(b=>b.setButtonText('保存凭证').setCta().onClick(async()=>{
      if(!value.trim()){new Notice('请填写自己的 API Key。');return;}
      try{await this.plugin.setKey(value.trim(),persist);value='';this.display();new Notice('凭证已应用，可回题库面板刷新额度。');}catch{new Notice('凭证保存失败，请重试。');}
    })).addButton(b=>b.setButtonText('清除凭证').onClick(async()=>{await this.plugin.clearKey();this.display();new Notice('已清除本插件使用的凭证。');}));
    node(containerEl,'p',this.plugin.getKey()?'当前状态：已配置自己的凭证。':'当前状态：尚未配置凭证。');
    node(containerEl,'p',`服务地址：${BASE}。获取教材目录和刷新额度不扣题目额度；获取题目会扣额。`);
    new Setting(containerEl).setName('PDF 导入使用的 Python').setDesc('填写已安装本地题库依赖的 Python 程序路径；留空使用系统 python。仅 PDF 和目录整理需要。').addText(t=>{t.setPlaceholder('例如 C:\\Python312\\python.exe');t.inputEl.value=this.plugin.settings.pythonPath||'';t.onChange(async value=>{this.plugin.settings.pythonPath=value.trim();await this.plugin.saveData(this.plugin.settings);});});
  }
}
export class BankView extends ItemView{
  constructor(leaf,plugin){super(leaf);this.plugin=plugin;this.scope={};this.mode='chapter';this.sourcePath='';this.nodes=[];this.knowledgeNodes=[];this.meta={};this.batch=null;this.lock=false;this.loading=false;this.epoch=0;this.queuedContext=null;this.closed=false;this.chapterOptions=new Map();this.expandedQuestions=new Set();}
  getViewType(){return VIEW;}getDisplayText(){return '题庄本地题库';}getIcon(){return 'library';}
  async onOpen(){this.draw();await this.loadInitial();await this.run(async()=>{
    if(await this.plugin.store.io.exists('.bank/pending/questions.json')){
      const data=JSON.parse(await this.plugin.store.io.read('.bank/pending/questions.json'));
      if(!['tizhuang.pending/v1','tizhuang.pending/v2'].includes(data.schema)||!Array.isArray(data.batch?.items)||data.batch.items.length>20)throw Error('上次取题缓存格式无效，请先检查缓存文件。');
      const directory=directoryNodes(data.batch.scope,data.batch.nodes);validateKnowledge(directory.knowledge);validateChapters(directory.chapters,data.batch.scope);requireScope(data.batch.scope,directory);this.batch=data.batch;await this.renderBatch();if(data.batch.items.some(i=>!i.saved))this.say('已恢复上次取题结果，可以继续保存，无需再次扣额。');
    }
  });}
  async onClose(){this.closed=true;this.epoch++;}
  select(parent,name,key,change){const field=node(parent,'div',null,'tz-select-field');label(field,name);const el=node(field,'select');el.setAttribute('aria-label',name);this.inputs[key]=el;this.options(key,[],'请先加载');el.addEventListener('change',async()=>{if(this.lock)return;this.scope[key]=el.value?Number(el.value):null;this.sourcePath='';if(key==='chapter_id'||key==='knowledge_tree_id'){this.mode=key==='chapter_id'?'chapter':'knowledge';const other=key==='chapter_id'?'knowledge_tree_id':'chapter_id';if(el.value&&this.scope[other]){this.scope[other]=null;this.inputs[other].value='';this.say(key==='chapter_id'?'已选章节，知识点筛选已清空。':'已选知识点，章节筛选已清空。');}}try{await change();this.updateContext();await this.remember();}catch(error){this.say(error.message||'切换失败，请重试。',true);}});return el;}
  options(key,values,placeholder='请选择'){const el=this.inputs[key],fragment=document.createDocumentFragment();const first=node(fragment,'option',placeholder);first.value='';for(const v of values){const o=node(fragment,'option',v.name);o.value=String(v.id);}el.replaceChildren(fragment);el.value=this.scope[key]?String(this.scope[key]):'';el.disabled=this.lock||!values.length;}
  reset(keys){for(const k of keys){this.scope[k]=null;this.options(k,[],'请先选择上级');}if(keys.includes('knowledge_tree_id'))this.knowledgeNodes=[];if(keys.includes('chapter_id')){this.nodes=[];this.chapterOptions.clear();}this.epoch++;this.loading=false;if(this.loadNotice)this.loadNotice.hidden=true;this.contentEl.setAttribute('aria-busy','false');this.setDisabled(this.lock);}
  async run(task){if(this.lock)return;this.lock=true;this.setDisabled(true);try{await task();}catch(e){this.say(e.message||'操作失败，请重试。',true);}finally{this.lock=false;this.setDisabled(false);this.updateContext();try{await this.remember();}catch{this.say('选择记忆保存失败，当前操作仍可继续。',true);}if(this.queuedContext){const next=this.queuedContext;this.queuedContext=null;await this.applyContext(next);}}}
  setDisabled(value){for(const el of this.contentEl.querySelectorAll('button,select,input'))el.disabled=value||el.dataset.saved==='true'||(el.tagName==='SELECT'&&el.options.length<=1);if(this.fetchButton)this.fetchButton.disabled=value||this.loading;if(this.quotaButton)this.quotaButton.disabled=value||Boolean(this.quotaBusy);this.updateSelection(value);}
  async load(task){if(this.lock)return;const seq=++this.epoch;this.loading=true;this.loadNotice.hidden=false;this.contentEl.setAttribute('aria-busy','true');this.setDisabled(false);try{await task();}catch(error){if(seq===this.epoch&&!this.closed)this.say(error.message||'目录加载失败，请重试。',true);}finally{if(seq===this.epoch&&!this.closed){this.loading=false;this.loadNotice.hidden=true;this.contentEl.setAttribute('aria-busy','false');this.setDisabled(this.lock);this.updateContext();try{await this.remember();}catch{this.say('选择记忆保存失败，当前操作仍可继续。',true);}}}}
  showQuota(remaining,used){this.quota.textContent=typeof remaining==='number'?`剩余 ${remaining} 题`:'额度待查询';this.quota.title=typeof remaining==='number'?`今日剩余题目额度：${remaining} 题${typeof used==='number'?` · 今日已用 ${used} 题`:''}`:'刷新查看今日题目额度';this.quota.setAttribute('aria-label',this.quota.title);}
  async refreshQuota(){if(this.quotaBusy)return;this.quotaBusy=true;this.quotaButton.disabled=true;try{const q=await this.plugin.api.quota();this.showQuota(q.remaining,q.used);this.say('额度已刷新。');}catch(error){this.say(error.message,true);}finally{this.quotaBusy=false;this.quotaButton.disabled=this.lock;}}
  say(text,error=false){this.status.textContent=text;this.status.classList.toggle('tz-error',error);}
  normalizeChoice(){if(this.scope.chapter_id&&this.scope.knowledge_tree_id)this.scope[this.mode==='knowledge'?'chapter_id':'knowledge_tree_id']=null;}
  directory(){return {chapters:this.nodes,knowledge:this.knowledgeNodes};}
  scopeText(){
    const value=(rows,id)=>rows?.find(v=>String(v.id)===String(id))?.name;
    return [value(this.meta.phases,this.scope.phase_id),value(this.meta.subjects,this.scope.subject_id),value(this.meta.editions,this.scope.edition_id),value(this.meta.grades,this.scope.grade_id),value(this.nodes,this.scope.chapter_id)||'不限章节',value(this.knowledgeNodes,this.scope.knowledge_tree_id)||'不限知识点'].filter(Boolean).join(' · ');
  }
  updateContext(){
    if(!this.contextLabel)return;
    const subject=this.meta.subjects?.find(v=>String(v.id)===String(this.scope.subject_id))?.name||'',phase=this.meta.phases?.find(v=>String(v.id)===String(this.scope.phase_id))?.name||'';
    const chapter=this.nodes.find(v=>String(v.id)===String(this.scope.chapter_id)),knowledge=this.knowledgeNodes.find(v=>String(v.id)===String(this.scope.knowledge_tree_id));
    const edition=this.meta.editions?.find(v=>String(v.id)===String(this.scope.edition_id))?.name;
    this.contextMeta.textContent=[phase,subject,edition].filter(Boolean).join(' · ')||'当前取题范围';
    this.contextLabel.textContent=[chapter?.name,knowledge?.name].filter(Boolean).join(' · ')||'不限章节 · 不限知识点';
    this.contextHint.textContent=!chapter&&!knowledge?['覆盖当前学段知识树',!this.scope.edition_id?'未限定教材':'',this.meta.grades?.find(v=>String(v.id)===String(this.scope.grade_id))?.name].filter(Boolean).join(' · '):!this.scope.edition_id?'未限定教材 · 可展开筛选，或打开左侧目录选择节点':this.meta.grades?.find(v=>String(v.id)===String(this.scope.grade_id))?.name||'可展开筛选，或打开左侧目录选择节点';
    this.contextLabel.title='打开左侧目录并定位节点';
    this.chapterRoute.textContent=chapter?'定位章节':'章节目录';this.knowledgeRoute.textContent=knowledge?'定位知识点':'知识点目录';
  }
  async remember(){if(!this.scope.subject_id||!this.scope.phase_id)return;await this.plugin.saveSelection({mode:this.mode,scope:{...this.scope},sourcePath:this.sourcePath,count:Number(this.count.value),solutions:this.solutions.checked,advancedOpen:this.advanced.open});}
  async applyContext(context){
    if(this.lock){this.queuedContext=context;return;}
    await this.load(async()=>{
      const seq=this.epoch;this.nodes=[];this.knowledgeNodes=[];this.chapterOptions.clear();
      this.mode=context.mode;this.scope={...context.scope};this.normalizeChoice();this.sourcePath=context.path||'';
      if(!this.meta.subjects?.length)await this.loadInitial(true,false);
      if(seq!==this.epoch)return;
      this.scope={...context.scope};this.normalizeChoice();this.options('subject_id',this.meta.subjects);this.options('phase_id',this.meta.phases);
      if(!this.inputs.subject_id.value||!this.inputs.phase_id.value)throw Error('当前笔记的学科学段不在网站目录中，请检查节点属性。');
      await this.loadScoped(true);if(seq!==this.epoch)return;if(this.scope.edition_id)await this.loadChapters(true);if(seq!==this.epoch)return;
      requireScope(this.scope,this.directory());this.advanced.open=false;this.updateContext();this.say('已带入左侧节点，可以直接获取题目。');
    });
  }
  draw(){
    const root=this.contentEl;root.replaceChildren();root.classList.add('tz-bank');this.inputs={};
    const shell=node(root,'div',null,'tz-shell');
    const header=node(shell,'header',null,'tz-header');renderBrand(header);
    const actions=node(header,'div',null,'tz-header-actions');const website=iconButton(actions,'打开题庄官网',()=>window.open('https://tizhuang.qcscience.cc/','_blank','noopener,noreferrer'),icons.website);website.classList.add('tz-website');
    renderNavigation(shell,this,'website');
    const workspace=node(shell,'div',null,'tz-workspace');
    const context=node(workspace,'div',null,'tz-context');const contextTop=node(context,'div',null,'tz-context-top');this.contextMeta=node(contextTop,'span',null,'tz-context-meta');iconButton(contextTop,'使用当前打开的节点',()=>this.plugin.useActiveFile(this),icons.node);this.contextLabel=button(node(context,'h3'),'',()=>this.plugin.openDirectory(this,this.scope.chapter_id?'chapter':'knowledge'),'quiet');this.contextLabel.classList.add('tz-context-link');this.contextHint=node(context,'p',null,'tz-context-hint');const routes=node(context,'div',null,'tz-context-routes');this.chapterRoute=button(routes,'章节目录',()=>this.plugin.openDirectory(this,'chapter'),'quiet');this.knowledgeRoute=button(routes,'知识点目录',()=>this.plugin.openDirectory(this,'knowledge'),'quiet');
    this.advanced=node(workspace,'details',null,'tz-advanced');const summary=node(this.advanced,'summary');node(summary,'span','筛选取题范围');node(summary,'span','教材 / 知识点','tz-filter-hint');this.advanced.open=this.plugin.settings.lastSelection?.advancedOpen??true;
    const grid=node(this.advanced,'div',null,'tz-grid');
    const reload=()=>{this.reset(['edition_id','grade_id','chapter_id','knowledge_tree_id']);return this.loadScoped();};
    this.select(grid,'学科','subject_id',reload);this.select(grid,'学段','phase_id',reload);
    this.chapterFields=node(grid,'div',null,'tz-grid');this.select(this.chapterFields,'教材版本（可选）','edition_id',()=>{this.reset(['chapter_id']);this.filterChapters();return this.loadChapters();});
    this.select(this.chapterFields,'年级 / 学期（可选）','grade_id',()=>{this.scope.chapter_id=null;this.filterChapters();this.say(this.loading?'正在加载所选教材，完成后会显示这个学期的章节。':`已按学期筛选 ${this.inputs.chapter_id.options.length-1} 个章节。`);});this.select(this.chapterFields,'章节（可选）','chapter_id',()=>{});
    this.knowledgeFields=node(grid,'div',null,'tz-grid');this.select(this.knowledgeFields,'知识点（可选）','knowledge_tree_id',()=>{});node(this.advanced,'p','章节和知识点二选一，也可以都不选。','tz-muted tz-filter-choice-hint');
    const more=node(this.advanced,'details',null,'tz-directory-tools');node(more,'summary','更多目录操作');button(more,'重新加载目录',()=>this.loadInitial(false,true,true),'quiet');node(more,'p','目录有更新或加载异常时再使用。','tz-muted');
    const remembered=this.plugin.settings.lastSelection||{};
    const controls=node(workspace,'div',null,'tz-fetch-controls');const countRow=node(controls,'label',null,'tz-count');node(countRow,'span','题数');this.count=node(countRow,'input');this.count.type='number';this.count.min='1';this.count.max='20';this.count.step='1';this.count.value=String(remembered.count>=1&&remembered.count<=20?remembered.count:5);this.count.setAttribute('aria-label','获取题数');this.count.title='每次获取 1—20 题';
    this.fetchButton=button(controls,'获取题目',()=>this.run(()=>this.fetch()),'primary');this.fetchButton.classList.add('tz-fetch');
    const options=node(workspace,'div',null,'tz-fetch-options');const check=node(options,'label',null,'tz-check');this.solutions=node(check,'input');this.solutions.type='checkbox';this.solutions.checked=Boolean(remembered.solutions);node(check,'span','含答案解析');check.title='保存答案和解析，供教师参考';
    const balance=node(options,'div',null,'tz-balance');this.quota=node(balance,'span',null,'tz-quota');this.showQuota();this.quotaButton=iconButton(balance,'刷新额度',()=>this.refreshQuota(),icons.refresh);iconButton(balance,'设置自己的凭证',()=>{this.app.setting.open();this.app.setting.openTabById(this.plugin.manifest.id);},icons.key);
    for(const event of ['change']){this.count.addEventListener(event,()=>this.remember());this.solutions.addEventListener(event,()=>this.remember());}this.advanced.addEventListener('toggle',()=>this.remember());
    node(workspace,'p','取题扣题目额度 · 保存不再扣额','tz-cost-hint');const directory=node(workspace,'div',null,'tz-directory-balance');this.directoryQuotaText=node(directory,'span','目录按学段 × 学科开通，默认 5 个；同一范围重复使用不扣。','tz-muted');button(directory,'目录额度',async()=>{try{if(!await this.plugin.api.directoryCapabilities(true)){this.directoryQuotaText.textContent='目录额度服务尚未发布，当前沿用原目录接口。';return;}const state=await this.plugin.api.directoryQuota();this.directoryQuotaText.textContent=`目录已开通 ${state.used} / ${state.limit} 个，剩余 ${state.remaining} 个。`;}catch(error){this.say(error.message,true);}},'quiet');
    this.loadNotice=node(shell,'p','正在加载目录，可继续切换……','tz-progress');this.loadNotice.hidden=true;this.loadNotice.setAttribute('role','status');
    this.status=node(shell,'p','正在加载学科和学段……','tz-status');this.status.setAttribute('role','status');this.status.setAttribute('aria-live','polite');this.results=node(shell,'div',null,'tz-results');
  }
  async loadInitial(inRun=false,restore=true,force=false){
    const wanted=restore?this.plugin.settings.lastSelection:null;
    const task=async()=>{const seq=this.epoch;const results=await Promise.all([this.plugin.api.meta('subjects',{}, {force}),this.plugin.api.meta('phases',{}, {force})]);if(seq!==this.epoch)return;this.meta.subjects=results[0];this.meta.phases=results[1];this.scope={};this.nodes=[];this.knowledgeNodes=[];this.chapterOptions.clear();
      if(wanted&&results[0].some(n=>n.id===wanted.scope?.subject_id)&&results[1].some(n=>n.id===wanted.scope?.phase_id)){this.mode=wanted.mode==='knowledge'?'knowledge':'chapter';this.scope={...wanted.scope};this.normalizeChoice();this.sourcePath=wanted.sourcePath||'';}
      await this.plugin.store.saveCatalog({subjects:results[0],phases:results[1]});this.options('subject_id',results[0]);this.options('phase_id',results[1]);for(const k of ['edition_id','grade_id','chapter_id','knowledge_tree_id'])this.options(k,[],'请先选择上级');
      if(this.scope.subject_id&&this.scope.phase_id){await this.loadScoped(true,force);if(seq!==this.epoch)return;if(this.scope.edition_id)await this.loadChapters(true,force);if(seq!==this.epoch)return;this.say(force?'目录已更新，当前选择已保留。':'已恢复上次选择。');}else this.say('可在左侧选择节点，或用高级筛选设置范围。');
    };
    if(inRun)return task();return this.load(task);
  }
  async loadScoped(inRun=false,force=false){
    if(!this.scope.subject_id||!this.scope.phase_id)return;
    const task=async()=>{const seq=this.epoch,s={...this.scope};const [editions,grades]=await Promise.all([this.plugin.api.meta('editions',{subject_id:s.subject_id,phase_id:s.phase_id},{force}),this.plugin.api.meta('grades',{phase_id:s.phase_id},{force}),this.loadKnowledge(true,force)]);if(seq!==this.epoch)return;this.meta.editions=editions;this.meta.grades=grades;await this.plugin.store.saveCatalog({editions});if(seq!==this.epoch)return;this.options('edition_id',editions,'不限教材版本');this.options('grade_id',grades,'全部年级 / 学期');if(this.scope.edition_id&&!this.inputs.edition_id.value){this.scope.edition_id=null;this.scope.chapter_id=null;}if(this.scope.grade_id&&!this.inputs.grade_id.value){this.scope.grade_id=null;this.scope.chapter_id=null;}this.filterChapters();this.say('章节和知识点二选一，也可以都不选。');};return inRun?task():this.load(task);
  }
  async loadKnowledge(inRun=false,force=false){const task=async()=>{const s={...this.scope},seq=this.epoch,path=`.bank/taxonomy/${s.subject_id}-${s.phase_id}.json`,params={subject_id:s.subject_id,phase_id:s.phase_id,limit:5000};if(!force&&await this.plugin.store.io.exists(path)){const saved=JSON.parse(await this.plugin.store.io.read(path));if(saved.subject_id!==s.subject_id||saved.phase_id!==s.phase_id)throw Error('本地知识树学科学段不一致。');validateKnowledge(saved.nodes);this.plugin.api.cache.seed('knowledge-points',params,saved.nodes,saved.downloaded_at);}const nodes=await this.plugin.api.meta('knowledge-points',params,{force});if(seq!==this.epoch)return;this.knowledgeNodes=validateKnowledge(nodes);if(this.directoryQuotaText)this.directoryQuotaText.textContent=this.plugin.api.directoryPolicy==='legacy'?'目录额度服务尚未发布，当前沿用原目录接口。':'目录按学段 × 学科开通，默认 5 个；同一范围重复使用不扣。';const map=new Map(nodes.map(n=>[n.id,n]));this.options('knowledge_tree_id',nodes.map(n=>{const names=[n.name];let p=map.get(n.parent_id);while(p){names.unshift(p.name);p=map.get(p.parent_id);}return {...n,name:names.join(' / ')};}),'不限知识点');if(s.knowledge_tree_id&&!this.inputs.knowledge_tree_id.value){this.scope.knowledge_tree_id=null;throw Error('上次知识点已不在目录中，请重新选择。');}};return inRun?task():this.load(task);}
  async loadChapters(inRun=false,force=false){
    if(!this.scope.edition_id)return;
    const task=async()=>{const s={...this.scope},seq=this.epoch,params={subject_id:s.subject_id,phase_id:s.phase_id,edition_id:s.edition_id,limit:1000},path=`.bank/textbooks/${s.subject_id}-${s.phase_id}-${s.edition_id}.json`;if(!force&&await this.plugin.store.io.exists(path)){const saved=JSON.parse(await this.plugin.store.io.read(path));validateChapters(saved.nodes,s);this.plugin.api.cache.seed('chapters',params,saved.nodes,saved.downloaded_at);}const data=await this.plugin.api.meta('chapters',params,{force});if(seq!==this.epoch)return;this.nodes=validateChapters(data,s);this.prepareChapters();this.filterChapters();if(this.scope.chapter_id&&!this.inputs.chapter_id.value){this.scope.chapter_id=null;throw Error('章节已不在当前版本目录中，请重新选择。');}this.say(`已加载 ${data.length} 个章节。切换学期会立即筛选。`);};return inRun?task():this.load(task);
  }
  prepareChapters(){
    const map=new Map(this.nodes.map(n=>[String(n.id),n]));
    const values=this.nodes.map(n=>{let parts=[n.name],p=map.get(String(n.parent_id));while(p){parts.unshift(p.name);p=map.get(String(p.parent_id));}const grade=this.meta.grades?.find(g=>String(g.id)===String(n.grade_id));return {...n,name:(grade?grade.name+' · ':'')+parts.join(' / ')};});
    this.chapterOptions.clear();this.chapterOptions.set('',values);for(const n of values){const key=String(n.grade_id);if(!this.chapterOptions.has(key))this.chapterOptions.set(key,[]);this.chapterOptions.get(key).push(n);}
  }
  filterChapters(){
    const values=this.chapterOptions.get(this.scope.grade_id?String(this.scope.grade_id):'')||[];
    this.options('chapter_id',values,values.length?'不限章节':this.scope.edition_id?'不限章节（当前条件暂无目录）':'不限章节（选教材后可细选）');
  }
  async fetch(){
    queryFilters(this.scope,this.directory());const count=Number(this.count.value);if(!Number.isInteger(count)||count<1||count>20)throw Error('每次获取题数须为 1 到 20。');
    if(!this.plugin.getKey())throw Error('请先在插件设置中填写自己的题庄 API Key。');
    if(this.batch?.items.some(i=>!i.saved))throw Error('上批题目尚未全部保存，请先保存或点击「清空结果」再获取，避免重复扣额。');
    const s={...this.scope};const title=this.scopeText()+(!s.chapter_id&&!s.knowledge_tree_id?'（当前学段知识树范围）':'');
    const yes=await new Promise(resolve=>new SpendModal(this.app,`${title}：最多获取 ${count} 题，使用自己的额度。`,resolve).open());if(!yes){this.say('已取消获取，未发送取题请求。');return;}
    // Check local format/writability before spending the user's quota.
    await this.plugin.store.init();await this.plugin.store.mkdir('.bank/pending');
    this.say('正在获取题目，请勿重复点击……');
    const solutions=this.solutions.checked;let data,before;const key=cursorKey(s);const offset=this.plugin.settings.cursors?.[key]||0;
    try{data=await this.plugin.api.questions(s,this.directory(),count,{offset,onQuota:q=>{before=q;this.showQuota(q.remaining,q.used);}});}catch(error){let check='';try{const after=await this.plugin.api.quota();this.showQuota(after.remaining,after.used);check=before?`请求前后今日已用额度：${before.used} → ${after.used} 题。`:'额度已刷新。';}catch{check='额度刷新失败，请稍后手动刷新。';}throw Error(error.message+'\n'+check);}
    // Retain the paid response before conversion/download: a save failure must not lose paid questions.
    this.batch={scope:s,nodes:structuredClone(this.directory()),solutions,items:data.items.map(raw=>({raw:redacted(raw,solutions),saved:false,selected:true,path:null}))};
    let cacheFailed=false;try{await this.persistBatch();}catch{cacheFailed=true;}
    if(data.items.length){this.plugin.settings.cursors={...this.plugin.settings.cursors,[key]:offset+data.items.length};try{await this.plugin.saveData(this.plugin.settings);}catch{cacheFailed=true;}}
    this.showQuota(data.quota_remaining_today);
    await this.renderBatch();this.say(data.items.length?`已获取 ${data.items.length} 题。保存到本地不再扣额。${cacheFailed?'取题缓存写入失败，请保持面板打开并立即保存。':''}`:(offset?'当前范围没有更多题目。可更换节点；不会自动放宽筛选条件。':'当前筛选范围没有匹配题目，可调整条件；不会自动放宽筛选条件。'),cacheFailed);
  }
  async persistBatch(){await this.plugin.store.io.write('.bank/pending/questions.json',JSON.stringify({schema:'tizhuang.pending/v2',batch:this.batch},null,2));}
  updateSelection(disabled=this.lock){
    if(!this.batch||!this.saveButton)return;
    const unsaved=this.batch.items.filter(i=>!i.saved),chosen=unsaved.filter(i=>i.selected).length;
    this.selectionLabel.textContent=`已选 ${chosen} / ${unsaved.length}`;
    this.selectAll.checked=unsaved.length>0&&chosen===unsaved.length;this.selectAll.indeterminate=chosen>0&&chosen<unsaved.length;this.selectAll.disabled=disabled||!unsaved.length;
    this.saveButton.textContent=chosen?`保存到本地 (${chosen})`:'保存到本地';this.saveButton.disabled=disabled||!chosen;
  }
  questionMetadata(raw){
    const knowledge=typeof raw.knowledges==='string'?raw.knowledges.split(/[,，、]/).map(s=>s.trim()).filter(Boolean):[];
    const difficulty=typeof raw.difficulty==='number'&&Number.isFinite(raw.difficulty)&&raw.difficulty>=0&&raw.difficulty<=5?raw.difficulty:null;
    const difficultyLabel=difficulty==null?null:difficulty<=2?'简单':difficulty>=4?'困难':'中等';
    return {knowledge:[...new Set(knowledge)],difficulty,difficultyLabel};
  }
  async renderQuestionDetails(region,item,q){
    const {raw}=item;
    if(!this.batch.solutions)node(region,'p','本次未包含答案解析。下次取题可勾选「含答案解析」。','tz-detail-empty');
    else if(!q)node(region,'p','题目格式异常，暂无法显示答案解析。','tz-detail-empty');
    else for(const [key,title]of [['answer','答案'],['analysis','解析']]){
      const section=node(region,'section',null,'tz-detail-section');node(section,'h4',title);const content=node(section,'div',null,'tz-preview');
      if(q[key]?.trim())await MarkdownRenderer.render(this.app,q[key],content,'',this);else node(content,'p',`网站未提供${title}。`,'tz-detail-empty');
    }
    const sourceFields=[['来源年份',Number.isInteger(raw.year)&&raw.year>0?raw.year:null],['来源地区',typeof raw.area==='string'?raw.area.trim():null],['原试卷来源',typeof raw.source==='string'?raw.source.trim():null],['来源题号',raw.id]].filter(([,value])=>value!=null&&value!=='');
    if(sourceFields.length){const footer=node(region,'footer',null,'tz-source-line');footer.setAttribute('aria-label','题目来源');for(const [title,value]of sourceFields){const field=node(footer,'span',String(value));field.title=title;}}
  }
  async renderBatch(){
    this.results.replaceChildren();this.saveButton=null;if(!this.batch||!this.batch.items.length)return;
    const toolbar=node(this.results,'div',null,'tz-result-toolbar');const selection=node(toolbar,'label',null,'tz-check tz-select-all');this.selectAll=node(selection,'input');this.selectAll.type='checkbox';this.selectAll.setAttribute('aria-label','全选未保存的题目');this.selectionLabel=node(selection,'span');
    this.selectAll.addEventListener('change',()=>{for(const item of this.batch.items)if(!item.saved)item.selected=this.selectAll.checked;for(const input of this.results.querySelectorAll('.tz-question input:not([data-saved="true"])')){input.checked=this.selectAll.checked;input.closest('.tz-question').classList.toggle('is-selected',input.checked);}this.updateSelection();});
    const actions=node(toolbar,'div',null,'tz-result-actions');this.saveButton=button(actions,'保存到本地',()=>this.run(()=>this.saveBatch()),'primary');iconButton(actions,'清空结果',()=>this.run(async()=>{if(await this.plugin.store.io.exists('.bank/pending/questions.json'))await this.plugin.store.io.remove('.bank/pending/questions.json');this.batch=null;this.saveButton=null;this.results.replaceChildren();this.say('结果已清空，已消耗的额度不会退回。');}),icons.clear);
    const list=node(this.results,'div',null,'tz-question-list');
    for(const [index,item]of this.batch.items.entries()){const card=node(list,'section',null,'tz-question');card.classList.toggle('is-selected',Boolean(item.selected&&!item.saved));card.classList.toggle('is-saved',Boolean(item.saved));const head=node(card,'div',null,'tz-question-head');const input=node(head,'input');input.type='checkbox';input.checked=item.selected;input.disabled=item.saved||this.lock;input.dataset.saved=String(Boolean(item.saved));input.setAttribute('aria-label',`勾选第 ${index+1} 道题`);input.addEventListener('change',()=>{item.selected=input.checked;card.classList.toggle('is-selected',input.checked);this.updateSelection();});node(head,'span',item.raw.question_type||'未分类','tz-type');
      const meta=this.questionMetadata(item.raw);if(meta.difficultyLabel)node(head,'span',meta.difficultyLabel,'tz-difficulty');
      const knowledge=node(head,'span',meta.knowledge.join(' · '),'tz-knowledge');knowledge.title=meta.knowledge.join('、');
      node(head,'span',item.saved?'已保存':'未保存','tz-local-status'+(item.saved?' tz-saved':''));if(item.path)iconButton(head,'打开本地题目',()=>this.app.workspace.openLinkText(item.path,'',false),icons.open);
      let q;try{q=questionFrom(item.raw,this.batch.scope,this.batch.solutions,markdown);const preview=node(card,'div',null,'tz-preview');await MarkdownRenderer.render(this.app,q.content,preview,'',this);}catch(e){node(card,'p',e.message,'tz-error');}
      const region=node(card,'div',null,'tz-question-details');region.hidden=true;region.id='tz-detail-'+crypto.randomUUID();region.setAttribute('role','region');region.setAttribute('aria-label',`第 ${index+1} 道题详情`);let rendered;
      const setOpen=async open=>{region.hidden=!open;toggle.textContent=open?'收起':'详情';toggle.setAttribute('aria-expanded',String(open));if(open){this.expandedQuestions.add(String(item.raw.id));rendered??=this.renderQuestionDetails(region,item,q).catch(()=>node(region,'p','详情显示失败，请重新打开题库面板。','tz-error'));await rendered;}else this.expandedQuestions.delete(String(item.raw.id));};
      const toggle=button(head,'详情',()=>setOpen(region.hidden),'quiet');toggle.classList.add('tz-detail-toggle');toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-controls',region.id);toggle.title='查看答案、解析和来源，不扣题目额度';toggle.disabled=this.lock;
      if(this.expandedQuestions.has(String(item.raw.id)))await setOpen(true);
    }
    this.updateSelection();
  }
  async saveBatch(){
    if(this.plugin.localTaskActive)throw Error('本地导入正在写入题库，请等待完成后保存。');
    if(!this.batch)return;let added=0,duplicates=0;const errors=[];
    const chosen=this.batch.items.filter(i=>i.selected&&!i.saved);if(!chosen.length){this.say('请选择尚未保存的题目。');return;}
    for(const item of chosen){try{
      this.say(`正在保存题号 ${item.raw.id}……`);
      const q=questionFrom(item.raw,this.batch.scope,this.batch.solutions,markdown);
      const prepared=await localize(q,requestUrl,document);
      const r=await this.plugin.store.save(prepared.question,this.batch.nodes,prepared.downloaded);
      item.saved=true;item.path=r.path;if(r.action==='duplicate')duplicates++;else added++;
      await this.persistBatch();
    }catch(e){errors.push(`题号 ${item.raw.id}：${e.message}`);}}
    await this.renderBatch();this.say(`新增 ${added} 题，已有 ${duplicates} 题。${errors.length?'\n'+errors.join('\n')+'\n可再次点击保存，无需重新取题。':'可在「题目库」中查看，或交给本地 skill 检索、组卷。'}`,Boolean(errors.length));
  }
}
export default class TeacherBankPlugin extends Plugin{
  async onload(){
    this.settings=await this.loadData()||{};this.sessionKey='';this.store=new Store(this.app.vault.adapter);this.basket=await new PaperBasket(this.store).load();this.api=new Api(requestUrl,()=>this.getKey(),{cache:new MetadataCache(this.store.io),scopedDirectories:true});
    this.registerView(VIEW,leaf=>new BankView(leaf,this));this.addSettingTab(new CredentialsTab(this.app,this));
    this.registerView(LIBRARY_VIEW,leaf=>new LibraryView(leaf,this));
    this.registerMarkdownCodeBlockProcessor?.('tizhuang-dashboard',(_source,el)=>{const actions=node(el,'div',null,'tz-actions');button(actions,'打开题库工作台',()=>this.openLibrary('home'),'primary');button(actions,'浏览我的题目',()=>this.openLibrary('questions'));button(actions,'导入 PDF',()=>this.openLibrary('pdf'));button(actions,'打开组卷篮',()=>this.openLibrary('basket'));});
    this.registerMarkdownCodeBlockProcessor?.('tizhuang-paper',async(_source,el,ctx)=>{const source=ctx?.sourcePath||'';if(!/^试卷\/[^/]+\/试卷\.md$/.test(source))return;const folder=source.slice(0,source.lastIndexOf('/')),actions=node(el,'div',null,'tz-actions');for(const [name,rel]of [['无答案 Word','打印稿/试卷.docx'],['教师答案 Word','教师稿/试卷.docx'],['无答案打印稿','打印稿/试卷.html'],['教师打印稿','教师稿/试卷.html']])if(await this.store.io.exists(folder+'/'+rel))button(actions,name,()=>this.openLocalOutput(this.app.vault.adapter.getBasePath()+'/'+folder+'/'+rel));});
    this.registerMarkdownPostProcessor((el,ctx)=>{
      for(const img of el.querySelectorAll('img')){const src=img.getAttribute('src')||'';const m=src.match(/^(?:\.\.\/)+((?:资料\/)?附件\/[a-f0-9]{64}\.(?:png|jpe?g|gif|webp))$/);if(m){const file=this.app.vault.getAbstractFileByPath(m[1]);if(file)img.src=this.app.vault.getResourcePath(file);}}
      if(ctx?.sourcePath?.startsWith('试卷/')&&ctx.sourcePath.endsWith('/试卷.md'))for(const link of el.querySelectorAll('a')){let href;try{href=decodeURIComponent(link.getAttribute('data-href')||link.getAttribute('href')||'');}catch{continue;}if(/^(打印稿|教师稿)\/试卷\.(html|docx)$/.test(href)){link.addEventListener('click',event=>{event.preventDefault();event.stopImmediatePropagation();this.openLocalOutput(this.app.vault.adapter.getBasePath()+'/'+ctx.sourcePath.slice(0,ctx.sourcePath.lastIndexOf('/'))+'/'+href);},true);}}
      const file=ctx?.sourcePath?this.app.vault.getAbstractFileByPath(ctx.sourcePath):null;const context=this.contextFor(file);
      if(context&&el.querySelector('h1')&&!el.querySelector('.tz-node-action')){const b=button(el,'浏览本地题目',async()=>{const view=await this.openLibrary('questions');await view?.fromContext(context);},'primary');b.classList.add('tz-node-action');el.prepend(b);const fetch=button(el,'从网站补题',()=>this.openFromContext(context));fetch.classList.add('tz-node-action');fetch.title='自动设置取题范围，确认后才扣减额度';}
    });
    this.registerEvent(this.app.workspace.on('file-menu',(menu,file)=>{const context=this.contextFor(file);if(context){menu.addItem(item=>item.setTitle('浏览本地题目').setIcon('library').onClick(async()=>{const view=await this.openLibrary('questions');await view?.fromContext(context);}));menu.addItem(item=>item.setTitle(context.mode==='chapter'?'从此章节获取题目':'从此知识点获取题目').setIcon('download').onClick(()=>this.openFromContext(context)));}}));
    this.registerEvent(this.app.workspace.on('file-open',file=>{if(this.routingDirectory)return;const context=this.contextFor(file);if(context){for(const leaf of this.app.workspace.getLeavesOfType(VIEW))leaf.view?.applyContext(context);for(const leaf of this.app.workspace.getLeavesOfType(LIBRARY_VIEW))leaf.view?.fromContext(context);}}));
    this.addRibbonIcon('library','打开题庄本地题库',()=>this.openLibrary('home'));this.addCommand({id:'open-teacher-bank',name:'打开本地题库',callback:()=>this.openLibrary('home')});
    this.addCommand({id:'open-paper-basket',name:'打开可视化组卷篮',callback:()=>this.openLibrary('basket')});this.addCommand({id:'browse-local-questions',name:'浏览本地题目',callback:()=>this.openLibrary('questions')});this.addCommand({id:'import-local-pdf',name:'导入 PDF 试卷',callback:()=>this.openLibrary('pdf')});this.addCommand({id:'fetch-website-questions',name:'从网站获取题目',callback:()=>this.open()});
    this.addCommand({id:'fetch-from-current-node',name:'从当前章节或知识点获取题目',callback:()=>this.useActiveFile()});
    const refresh=file=>{if(!file?.path?.startsWith('题目库/'))return;clearTimeout(this.refreshTimer);this.refreshTimer=setTimeout(()=>{if(!this.localTaskActive)for(const leaf of this.app.workspace.getLeavesOfType(LIBRARY_VIEW))leaf.view?.refresh();},300);};if(this.app.vault.on)for(const name of ['create','modify','delete','rename'])this.registerEvent(this.app.vault.on(name,refresh));
  }
  contextFor(file){if(!file)return null;let target=file;if(file.extension!=='md')target=this.app.vault.getAbstractFileByPath(file.path+'.md');if(!target)return null;return contextFromProperties(this.app.metadataCache.getFileCache(target)?.frontmatter,target.path);}
  async openDirectory(view,kind){try{await openDirectory(this,view,kind);}catch(error){view.say(error.message||'目录打开失败，请重试。',true);}}
  async useActiveFile(view){const context=this.contextFor(this.app.workspace.getActiveFile());if(!context){new Notice('请先在左侧打开一个带章节编号或知识节点编号的节点笔记。');return;}if(view)return view.applyContext(context);return this.openFromContext(context);}
  async openFromContext(context){const view=await this.open();if(view)await view.applyContext(context);}
  async saveSelection(selection){this.settings.lastSelection=selection;await this.saveData(this.settings);}
  getKey(){return this.sessionKey||((this.settings.secretId&&this.app.secretStorage?.getSecret(this.settings.secretId))||'');}
  async setKey(key,persist){
    if(persist&&this.app.secretStorage){const id=this.settings.secretId||'tizhuang-question-bank-'+crypto.randomUUID().replaceAll('-','');this.app.secretStorage.setSecret(id,key);this.settings.secretId=id;this.sessionKey='';await this.saveData(this.settings);}else{await this.clearKey();this.sessionKey=key;}
  }
  async clearKey(){if(this.settings.secretId&&this.app.secretStorage)this.app.secretStorage.setSecret(this.settings.secretId,'');this.sessionKey='';delete this.settings.secretId;await this.saveData(this.settings);}
  async open(preferredLeaf){let leaf=preferredLeaf||this.app.workspace.getLeavesOfType(VIEW)[0];if(!leaf||leaf.view?.getViewType?.()!==VIEW){leaf=leaf||this.app.workspace.getLeaf('tab');if(!leaf){new Notice('无法打开题库面板。');return;}await leaf.setViewState({type:VIEW,active:true});}await this.app.workspace.revealLeaf(leaf);return leaf.view;}
  async openLibrary(tab='home',preferredLeaf){let leaf=preferredLeaf||this.app.workspace.getLeavesOfType(LIBRARY_VIEW)[0];if(!leaf||leaf.view?.getViewType?.()!==LIBRARY_VIEW){leaf=leaf||this.app.workspace.getLeaf('tab');if(!leaf)return;await leaf.setViewState({type:LIBRARY_VIEW,active:true});}await this.app.workspace.revealLeaf(leaf);if(leaf.view?.show)await leaf.view.show(tab);return leaf.view;}
  async openLocalOutput(value){
    const base=this.app.vault.adapter.getBasePath().replace(/\\/g,'/').replace(/\/$/,''),path=String(value).replace(/\\/g,'/');
    if(!path.toLowerCase().startsWith((base+'/试卷/').toLowerCase())||path.split('/').includes('..')||!/^.+\/(打印稿|教师稿)\/试卷\.(html|docx)$/.test(path)){new Notice('试卷输出路径无效');return;}
    try{const error=await require('electron').shell.openPath(path);if(error)new Notice('打开失败：'+error);}catch(error){new Notice('请从试卷记录中打开文件：'+error.message);}
  }
  runLocal(command,args){return runLocal(this,command,args);}
  onunload(){this.sessionKey='';clearTimeout(this.refreshTimer);}
}
export {LibraryView};
