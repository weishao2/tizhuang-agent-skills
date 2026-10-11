import {AutoClassifyModal} from './classification-view.js';
import {renderNavigation} from './navigation.js';
import {renderBrand} from './brand.js';
import {ItemView,Modal,MarkdownRenderer,Notice} from 'obsidian';
import {LocalCatalog} from './library-core.js';
import {cleanTitle,hasImage,nativeTags} from './presentation.js';
import {hash} from './core.js';
import {drawBasket,basketBar,updateBasketBar} from './paper-view.js';
export const LIBRARY_VIEW='tizhuang-local-library';
const E=(p,t,text,cls)=>{const e=document.createElement(t);if(text!=null)e.textContent=text;if(cls)e.className=cls;p.append(e);return e;};
const B=(p,text,fn,cls='tz-quiet')=>{const b=E(p,'button',text,cls);b.type='button';b.onclick=fn;return b;};
const select=(p,title,entries,value,fn)=>{const label=E(p,'label',title,'tz-label'),el=E(label,'select');el.setAttribute('aria-label',title);for(const [id,name]of entries){const o=E(el,'option',name);o.value=id;}el.value=value||'';el.onchange=()=>fn(el.value);return el;};

class ClassifyModal extends Modal{
 constructor(app,catalog,row,done){super(app);this.catalog=catalog;this.row=row;this.done=done;}
 onOpen(){
  const root=this.contentEl;root.classList.add('tz-classify');E(root,'h2','整理分类与标签');E(root,'p',cleanTitle(this.row.q.title));
  const label=E(root,'label','标签（用逗号分隔，斜杠表示层级）'),tags=E(label,'textarea');tags.value=this.row.q.tags.join(', ');tags.rows=3;
  const tree=this.catalog.trees.find(t=>t.kind==='knowledge'&&this.catalog.treeMatch(this.row.q,t));const selected=new Set(this.row.q.knowledge_tree_ids);
  E(root,'p','关联知识点：可多选，教材章节保留原关联。','tz-muted');const search=E(root,'input');search.placeholder='查找知识点';search.setAttribute('aria-label','查找知识点');const list=E(root,'div',null,'tz-knowledge-picker');
  const draw=()=>{list.replaceChildren();for(const n of tree?.nodes||[]){if(search.value&&!n.name.includes(search.value))continue;const line=E(list,'label'),c=E(line,'input');c.type='checkbox';c.checked=selected.has(String(n.id));c.onchange=()=>c.checked?selected.add(String(n.id)):selected.delete(String(n.id));E(line,'span',n.name);}if(!tree)E(list,'p','该学科学段尚未下载知识树，可以先保存标签。');};draw();search.oninput=draw;
  const status=E(root,'p',null,'tz-status'),actions=E(root,'div',null,'tz-actions');B(actions,'取消',()=>this.close());const save=B(actions,'保存分类',async()=>{save.disabled=true;try{await this.catalog.classify(this.row.path,{tags:nativeTags(tags.value),knowledge:[...selected]});this.close();await this.done();}catch(error){status.textContent=error.message;save.disabled=false;}},'tz-primary');
 }
 onClose(){this.contentEl.replaceChildren();}
}

export class LibraryView extends ItemView{
 constructor(leaf,plugin){super(leaf);this.plugin=plugin;this.catalog=new LocalCatalog(plugin.store);this.filter={...(plugin.settings.libraryFilter||{})};this.tab=plugin.settings.libraryTab||'home';this.dimension=plugin.settings.libraryDimension||'chapter';this.sequence=0;this.closed=false;this.pdfBusy=false;}
 getViewType(){return LIBRARY_VIEW;}getDisplayText(){return '题庄本地题库';}getIcon(){return 'library';}
 async onOpen(){await this.refresh();}
 async onClose(){this.closed=true;this.sequence++;clearTimeout(this.searchTimer);}
 async refresh(){if(this.pdfBusy||this.plugin.basket?.busy)return;const seq=++this.sequence;try{await this.plugin.basket.queue;await this.plugin.basket.load();await this.catalog.load();if(this.closed||seq!==this.sequence)return;this.draw();const cfg=await this.plugin.store.json('.bank/config.json');if(cfg.ui_layout==='teacher/v2')await this.catalog.writeHome();}catch(error){this.contentEl.replaceChildren();E(this.contentEl,'p',error.message,'tz-error');}}
 async remember(){this.plugin.settings.libraryTab=this.tab;this.plugin.settings.libraryFilter={...this.filter};this.plugin.settings.libraryDimension=this.dimension;await this.plugin.saveData(this.plugin.settings);}
 async show(tab,filter){this.tab=tab;if(filter)this.filter=filter;await this.remember();this.draw();}
 async fromContext(context){this.tab='questions';this.dimension=context.mode==='chapter'?'chapter':'knowledge';this.filter={kind:this.dimension,scope:[context.scope.subject_id,context.scope.phase_id,...(this.dimension==='chapter'?[context.scope.edition_id]:[])].join('-'),node:String(context.scope.chapter_id||context.scope.knowledge_tree_id)};await this.refresh();await this.remember();}
 draw(){
  const root=this.contentEl;root.replaceChildren();root.classList.add('tz-bank','tz-library');const shell=E(root,'div',null,'tz-shell');const head=E(shell,'header',null,'tz-header');renderBrand(head);const actions=E(head,'div',null,'tz-header-actions');B(actions,'刷新',()=>this.refresh());const website=B(actions,'',()=>window.open('https://tizhuang.qcscience.cc/','_blank','noopener,noreferrer'));website.classList.add('tz-icon-button');website.title='打开题庄官网';website.setAttribute('aria-label','打开题庄官网');website.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18"/></svg>';
  renderNavigation(shell,this,this.tab);
  this.status=E(shell,'p',null,'tz-status');if(this.catalog.errors.length){E(shell,'p',`${this.catalog.errors.length} 个文件需要检查，其余题目可正常浏览。`,'tz-error');const details=E(shell,'details');E(details,'summary','查看异常文件');for(const item of this.catalog.errors)B(details,item.path+'：'+item.message,()=>this.openFile(item.path));}
  this.body=E(shell,'div',null,'tz-lib-body');if(this.tab==='home')this.home();else if(this.tab==='pdf')this.pdf();else if(this.tab==='basket')drawBasket(this);else this.questions();
 }
 openFile(path){return this.app.workspace.openLinkText(path,'',false);}
 batchRow(parent,batch){
  const line=E(parent,'div',null,'tz-import-row');E(line,'strong',batch.filename);const labels={prepared:'待 Agent 还原正文',partial:'部分导入，可继续',needs_agent:'待 Agent 识别',imported:'已导入，待核对'};E(line,'span',`${batch.pages.length} 页 · ${Object.keys(batch.imported||{}).length} 题已入库 · ${labels[batch.status]||'待处理'}`);
  const actions=E(line,'div',null,'tz-actions');if(Object.keys(batch.imported||{}).length)B(actions,'自动分类',()=>new AutoClassifyModal(this,batch.id).open());if(batch.reportPath)B(actions,'查看报告',()=>this.openFile(batch.reportPath));
  if(batch.status==='partial'&&batch.representation==='editable')B(actions,'继续导入',async()=>{if(this.pdfBusy)return;this.pdfBusy=true;try{await this.plugin.runLocal('pdf-import',['--batch',batch.id]);new Notice('已导入草稿并尝试关联知识点；请查看分类报告并核对题目。');}catch(error){new Notice(error.message);}finally{this.pdfBusy=false;await this.refresh();}});
  if(batch.status!=='imported'&&!(batch.status==='partial'&&batch.representation==='editable'))B(actions,'复制 Agent 指令',async()=>{const prompt=`使用 tizhuang-local-bank，在题库“${this.app.vault.adapter.getBasePath()}”中继续 PDF 导入批次 ${batch.id}。查看全部原页，将题干、选项、公式和表格还原为可编辑 Markdown/LaTeX，单独提取配图。去掉正文原题号和图片中的“第几题图”，原编号只留在来源记录，保留小问与图①等对应关系。核对原答案，根据考查内容关联到本地标准知识点树，综合题可关联多个知识点，不能只有标签；未指定教材不补章节。用 v2 分题清单导入待核对题目。`;try{await window.navigator.clipboard.writeText(prompt);new Notice('已复制。');}catch{const area=E(line,'textarea');area.value=prompt;area.readOnly=true;area.select();new Notice('请复制已选中的指令。');}});
 }
 home(){
  const hero=E(this.body,'section',null,'tz-lib-hero');E(hero,'div','我的教学资产','tz-eyebrow');E(hero,'h1','好题，都在这里。');E(hero,'p','按章节备课，按考点找题，把自己的试卷慢慢积累下来。');const actions=E(hero,'div',null,'tz-actions');B(actions,'浏览我的题目',()=>this.show('questions',{}),'tz-primary');B(actions,'导入一份 PDF',()=>this.show('pdf'));
  const stats=E(this.body,'div',null,'tz-stats');for(const [title,count,fn]of [['全部题目',this.catalog.rows.length,()=>this.show('questions',{})],['待核对',this.catalog.rows.filter(r=>r.q.status!=='reviewed').length,()=>this.show('questions',{status:'draft'})],['待分类',this.catalog.rows.filter(r=>!r.q.knowledge_tree_ids.length&&!r.q.chapter_ids.length).length,()=>this.show('questions',{unclassified:true})],['已组试卷',this.catalog.papers.length,()=>this.body.querySelector('.tz-paper-list').scrollIntoView({block:'nearest'})]]){const b=B(stats,'',fn,'tz-stat');E(b,'strong',String(count));E(b,'span',title);}
  const columns=E(this.body,'div',null,'tz-home-columns'),recent=E(columns,'section',null,'tz-home-section');E(recent,'h3','最近保存');for(const row of [...this.catalog.rows].sort((a,b)=>String(b.q.created_at).localeCompare(String(a.q.created_at))).slice(0,6)){const b=B(recent,'',()=>this.openFile(row.path),'tz-recent-row');if(hasImage(row.q))E(b,'span','[图]','tz-image-label');E(b,'span',cleanTitle(row.q.title,row.q.type));E(b,'small',row.q.status==='reviewed'?'已核对':'待核对');}if(!this.catalog.rows.length)E(recent,'p','先导入 PDF，或从网站保存几道题。','tz-muted');
  const activity=E(columns,'section',null,'tz-home-section');E(activity,'h3','导入进度');for(const batch of this.catalog.imports.slice(0,5))this.batchRow(activity,batch);if(!this.catalog.imports.length)E(activity,'p','暂无导入任务。','tz-muted');
  const papers=E(this.body,'section',null,'tz-home-section tz-paper-list');E(papers,'h3','我的试卷');for(const path of this.catalog.papers)B(papers,this.catalog.paperTitles.get(path),()=>this.openFile(path),'tz-recent-row');if(!this.catalog.papers.length)E(papers,'p','先核对题目，再告诉 Agent：“按本章已核对的题组一份练习卷。”','tz-muted');
  const more=E(this.body,'details',null,'tz-lib-resources');E(more,'summary','教学笔记与资料');E(more,'p','原件、图片和目录集中放在「资料」，日常从题目详情查看即可。');B(more,'打开题库首页笔记',()=>this.openFile('题库首页.md'));B(more,'查看待整理任务',()=>this.show('pdf'));
 }
 questions(){
  const bar=E(this.body,'div',null,'tz-local-filters'),search=E(bar,'input');search.type='search';search.placeholder='搜索题干、标签或导入文字';search.setAttribute('aria-label','搜索本地题目');search.value=this.filter.query||'';search.oninput=()=>{this.filter.query=search.value;clearTimeout(this.searchTimer);this.searchTimer=setTimeout(()=>{this.renderRows();this.remember();},160);};
  select(bar,'审核',[['','全部状态'],['draft','待核对'],['reviewed','已核对']],this.filter.status,value=>{this.filter.status=value;this.renderRows();this.remember();});
  select(bar,'题型',[['','全部题型'],...[...new Set(this.catalog.rows.map(r=>r.q.type||'未分类'))].map(t=>[t,t])],this.filter.type,value=>{this.filter.type=value;this.renderRows();this.remember();});
  B(bar,'重置筛选',()=>this.show('questions',{}));const tools=E(this.body,'div',null,'tz-classify-actions');B(tools,'自动分类',()=>new AutoClassifyModal(this).open(),'tz-secondary');E(tools,'span',this.catalog.rows.filter(r=>!r.q.knowledge_tree_ids.length).length+' 题未关联知识点','tz-muted');basketBar(this,this.body);
  const layout=E(this.body,'div',null,'tz-library-layout');this.treeArea=E(layout,'aside',null,'tz-tree-panel');select(this.treeArea,'分类方式',[['chapter','教材章节'],['knowledge','知识点'],['tags','标签']],this.dimension,value=>{this.dimension=value;this.filter={query:this.filter.query,status:this.filter.status,type:this.filter.type};this.drawTree();this.renderRows();this.remember();});this.tree=E(this.treeArea,'div',null,'tz-tree');this.rowsArea=E(layout,'section',null,'tz-local-results');this.drawTree();this.renderRows();
 }
 drawTree(){
  this.tree.replaceChildren();B(this.tree,`全部题目 · ${this.catalog.rows.length}`,()=>this.pick({}), 'tz-tree-item');
  const walk=(parent,nodes,parentId,pick)=>{for(const n of nodes.filter(n=>String(n.parent_id||'')===String(parentId||''))){const count=n.count??n.ids?.size??0;if(!count)continue;const children=nodes.some(c=>String(c.parent_id)===String(n.id)&&((c.count??c.ids?.size)||0));if(children){const detail=E(parent,'details');detail.open=true;const summary=E(detail,'summary');B(summary,n.name+` · ${count}`,()=>pick(n),'tz-tree-item');walk(detail,nodes,n.id,pick);}else B(parent,n.name+` · ${count}`,()=>pick(n),'tz-tree-item');}};
  if(this.dimension==='tags')walk(this.tree,this.catalog.tagTree(),'',n=>this.pick({tag:n.id}));
  else for(const tree of this.catalog.trees.filter(t=>t.kind===this.dimension)){const rows=this.catalog.rows.filter(r=>this.catalog.treeMatch(r.q,tree));if(!rows.length)continue;const group=E(this.tree,'details');group.open=true;E(group,'summary',this.catalog.scopeTitle(tree),'tz-tree-scope');const field=tree.kind==='chapter'?'chapter_ids':'knowledge_tree_ids';const nodes=tree.nodes.map(n=>{const ids=this.catalog.descendants(tree,n.id);return {...n,count:rows.filter(r=>r.q[field].some(id=>ids.has(String(id)))).length};});walk(group,nodes,'',n=>this.pick({kind:tree.kind,scope:tree.scope,node:String(n.id)}));}
  B(this.tree,'待分类',()=>this.pick({unclassified:true}),'tz-tree-item');
 }
 pick(scope){this.filter={query:this.filter.query,status:this.filter.status,type:this.filter.type,...scope};this.renderRows();this.remember();}
 async renderRows(){
  this.rowsArea.replaceChildren();const rows=this.catalog.select(this.filter);const title=E(this.rowsArea,'div',null,'tz-local-summary');let label=this.filter.tag||'';const tree=this.catalog.trees.find(t=>t.kind===this.filter.kind&&t.scope===this.filter.scope);if(tree)label=tree.nodes.find(n=>String(n.id)===this.filter.node)?.name||this.catalog.scopeTitle(tree);E(title,'strong',(this.filter.unclassified?'待分类':label||'全部题目')+` · ${rows.length} 题`);
  B(title,'勾选当前结果（'+Math.min(rows.length,100)+'）',async()=>{try{await this.plugin.basket.add(rows.slice(0,100).map(r=>r.q));this.renderRows();updateBasketBar(this);}catch(error){new Notice(error.message);}});if(tree&&this.filter.node)B(title,'网站补题',()=>this.plugin.openFromContext({mode:tree.kind==='chapter'?'chapter':'knowledge',scope:{subject_id:tree.subject_id,phase_id:tree.phase_id,...(tree.kind==='chapter'?{edition_id:tree.edition_id,chapter_id:Number(this.filter.node)}:{knowledge_tree_id:Number(this.filter.node)})}}));
  if(!rows.length){E(this.rowsArea,'p','当前分类没有匹配的本地题目。可调整筛选、导入资料或从网站补题。','tz-local-empty');return;}
  const list=E(this.rowsArea,'div',null,'tz-question-list');for(const row of rows.slice(0,100)){const {q}=row,card=E(list,'article',null,'tz-question tz-local-card'),head=E(card,'div',null,'tz-question-head');const check=E(head,'input');check.type='checkbox';check.checked=this.plugin.basket.has(q.id);check.setAttribute('aria-label','加入组卷篮：'+cleanTitle(q.title));card.classList.toggle('is-selected',check.checked);check.onchange=async()=>{try{if(check.checked)await this.plugin.basket.add([q]);else await this.plugin.basket.remove(q.id);card.classList.toggle('is-selected',check.checked);updateBasketBar(this);}catch(error){check.checked=this.plugin.basket.has(q.id);new Notice(error.message);}};E(head,'span',q.type||'未分类','tz-type');if(typeof q.difficulty==='number')E(head,'span',q.difficulty<=2?'简单':q.difficulty>=4?'困难':'中等','tz-difficulty');E(head,'span',q.tags.join(' · '),'tz-knowledge');E(head,'span',q.status==='reviewed'?'已核对':'待核对','tz-local-status');
   const title=E(card,'div',null,'tz-local-title');if(hasImage(q))E(title,'span','[图]','tz-image-label');E(title,'span',cleanTitle(q.title,q.type));
   const actions=E(card,'div',null,'tz-local-card-actions');const detail=E(card,'div',null,'tz-question-details');detail.hidden=true;let rendered=false;
   B(actions,'展开题目',async event=>{detail.hidden=!detail.hidden;event.currentTarget.textContent=detail.hidden?'展开题目':'收起';if(!rendered){for(const [key,name]of [['content','题目'],['answer','答案'],['analysis','解析']]){if(!q[key])continue;const section=E(detail,'section',null,'tz-detail-section');E(section,'h4',name);const content=E(section,'div',null,'tz-preview');let text=q[key].replace(/Assets\/([a-f0-9]+\.[a-z0-9]+)/g,(_,file)=>{const path=this.plugin.store.assetDir+'/'+file;const target=this.app.vault.getAbstractFileByPath(path);return target?this.app.vault.getResourcePath(target):path;});await MarkdownRenderer.render(this.app,text,content,row.path,this);}E(detail,'footer',q.source.label||'本地题目','tz-source-line');rendered=true;}});
   B(actions,'打开笔记',()=>this.openFile(row.path));B(actions,'分类 / 标签',()=>new ClassifyModal(this.app,this.catalog,row,()=>this.refresh()).open());
  }
  if(rows.length>100)E(this.rowsArea,'p',`显示前 100 题，共 ${rows.length} 题。请按章节或标签进一步筛选。`,'tz-muted');
 }
 pdf(){
  E(this.body,'h2','把试卷变成自己的题库');E(this.body,'p','文字与公式可编辑，配图单独保存；导入后先核对，再组卷。','tz-muted');const panel=E(this.body,'section',null,'tz-pdf-panel');
  const file=E(panel,'input');file.type='file';file.accept='.pdf,application/pdf';file.setAttribute('aria-label','选择 PDF 试卷');file.hidden=true;const chosen=E(panel,'p','支持文字和扫描 PDF','tz-muted');B(panel,'选择 PDF 试卷',()=>file.click(),'tz-secondary');file.onchange=()=>{chosen.textContent=file.files?.[0]?.name||'尚未选择文件';};const grid=E(panel,'div',null,'tz-grid');const scope={...(this.plugin.settings.lastPdfScope||this.plugin.settings.lastSelection?.scope||{})};delete scope.knowledge_tree_id;
  const entries=(dict)=>[['','未指定'],...Object.entries(dict||{})];let edition,chapter;
  const chapters=()=>{chapter.replaceChildren();for(const [id,name]of [['','待分类'],...(this.catalog.trees.find(t=>t.kind==='chapter'&&String(t.subject_id)===String(scope.subject_id)&&String(t.phase_id)===String(scope.phase_id)&&String(t.edition_id)===String(scope.edition_id))?.nodes||[]).map(n=>[String(n.id),n.name])]){const o=E(chapter,'option',name);o.value=id;}chapter.value=String(scope.chapter_id||'');};
  const editions=()=>{edition.replaceChildren();const ids=[...new Set(this.catalog.trees.filter(t=>t.kind==='chapter'&&String(t.subject_id)===String(scope.subject_id)&&String(t.phase_id)===String(scope.phase_id)).map(t=>String(t.edition_id)))];for(const [id,name]of [['','未指定教材'],...ids.map(id=>[id,this.catalog.names.editions?.[id]||`教材${id}`])]){const o=E(edition,'option',name);o.value=id;}edition.value=String(scope.edition_id||'');scope.edition_id=edition.value;chapters();};
  select(grid,'学科',entries(this.catalog.names.subjects),String(scope.subject_id||''),value=>{scope.subject_id=value;scope.edition_id='';scope.chapter_id='';editions();});select(grid,'学段',entries(this.catalog.names.phases),String(scope.phase_id||''),value=>{scope.phase_id=value;scope.edition_id='';scope.chapter_id='';editions();});edition=select(grid,'教材版本（可选）',[],null,value=>{scope.edition_id=value;scope.chapter_id='';chapters();});chapter=select(grid,'章节（可选）',[],null,value=>{scope.chapter_id=value;});editions();
  const message=E(panel,'p',null,'tz-status');const run=B(panel,'准备导入',async()=>{if(this.pdfBusy)return;const selected=file.files?.[0];if(!selected){message.textContent='请先选择一份 PDF。';return;}if(selected.size>100*1024*1024){message.textContent='每份 PDF 请控制在 100 MB 以内。';return;}this.pdfBusy=true;run.disabled=true;message.textContent='正在本地处理，请稍候……';try{
    const bytes=await selected.arrayBuffer(),sha=await hash(bytes),name=selected.name.replace(/[<>:"/\\|?*]/g,'_');const input='待整理/待导入PDF/'+sha.slice(0,8)+'-'+name;await this.plugin.store.mkdir('待整理/待导入PDF');await this.plugin.store.io.writeBinary(input,bytes);this.plugin.settings.lastPdfScope=scope;await this.plugin.saveData(this.plugin.settings);
    const args=['--file',this.app.vault.adapter.getBasePath()+'/'+input];for(const [key,opt]of [['subject_id','--subject'],['phase_id','--phase'],['edition_id','--edition'],['chapter_id','--chapter']])if(scope[key])args.push(opt,String(scope[key]));let result=await this.plugin.runLocal('pdf-prepare',args);
    if(await this.plugin.store.io.exists(input))await this.plugin.store.io.remove(input);

    message.textContent=result.status==='imported'?`已导入 ${result.imported} 题，请核对正文、配图、答案和分类。`:'已保存原页。复制下方指令，让 Agent 还原可编辑正文和独立配图。';
    B(panel,'打开导入报告',()=>this.openFile(result.report));
    if(result.status!=='imported'){const prompt=`使用 tizhuang-local-bank，在题库“${this.app.vault.adapter.getBasePath()}”中继续 PDF 导入批次 ${result.batch}。查看全部原页，将题干、选项、公式和表格还原为可编辑 Markdown/LaTeX，单独提取配图。去掉正文原题号和图片中的“第几题图”，原编号只留在来源记录，保留小问与图①等对应关系。核对原答案，根据考查内容关联到本地标准知识点树，综合题可关联多个知识点，不能只有标签；未指定教材不补章节。用 v2 分题清单导入待核对题目。`;const area=E(panel,'textarea');area.value=prompt;area.readOnly=true;area.rows=4;B(panel,'复制 Agent 指令',async()=>{try{await window.navigator.clipboard.writeText(prompt);new Notice('已复制。');}catch{area.focus();area.select();new Notice('请复制已选中的指令。');}});}
    await this.catalog.load();await this.catalog.writeHome();
   }catch(error){message.textContent=error.message;}finally{this.pdfBusy=false;run.disabled=false;}},'tz-primary');
  E(panel,'p','插件在本地准备原页和文字候选，再由 Agent 核对并还原题目。原 PDF 保留以便回查，不使用网站题目额度；模型是否在本地运行取决于所用 Agent。','tz-pdf-note');
  const history=E(this.body,'section',null,'tz-home-section');E(history,'h3','最近的 PDF 导入');for(const batch of this.catalog.imports.slice(0,10))this.batchRow(history,batch);
 }
}
