'use strict';
// Independent extension of Studio. All mutations use the same revisioned service.
let lf={catalog:'',node:'',tag:'',status:'',type:'',query:'',unused:false,archived:false,subject:'',page:0};
let librarySelected=new Set(),pdfSelection='',backups=[];
let initialCatalogRequested=false;
let savedDirectoryId='',directoryPreferenceLoaded=false,directoryCleared=false;
const directoryKey=()=>`tizhuang:directory:${state.workspace}`;
function saveDirectoryPreference(){try{localStorage.setItem(directoryKey(),JSON.stringify({id:savedDirectoryId,cleared:directoryCleared,scope,mode:filterMode}));}catch{}}
function useSavedDirectory(c,node=''){
  savedDirectoryId=c.id;directoryCleared=false;
  scope={subject_id:String(c.subject_id),phase_id:String(c.phase_id)};
  filterMode=c.kind;fetchOffset=0;
  nodes=c.kind==='knowledge'?c.nodes:[];chapters=c.kind==='chapter'?c.nodes:[];
  if(c.kind==='chapter')scope.edition_id=String(c.edition_id);
  if(node&&c.nodes.some(n=>String(n.id)===String(node)))scope[c.kind==='chapter'?'chapter_id':'knowledge_tree_id']=String(node);
  saveDirectoryPreference();
}
function initializeDirectoryPreference(){
  if(directoryPreferenceLoaded)return;
  directoryPreferenceLoaded=true;
  let pref={};try{pref=JSON.parse(localStorage.getItem(directoryKey())||'{}')||{};}catch{}
  const remembered=Object.fromEntries(Object.entries(pref.scope||{}).filter(([k,v])=>['subject_id','phase_id','edition_id','chapter_id','knowledge_tree_id','grade_id'].includes(k)&&/^\d+$/.test(String(v))));
  directoryCleared=pref.cleared===true;
  if(directoryCleared){scope=remembered;filterMode=pref.mode==='chapter'?'chapter':'knowledge';return;}
  const c=state.catalogs.find(c=>c.id===pref.id)||state.catalogs.find(c=>c.id===lf.catalog)||state.catalogs[0];
  if(c){useSavedDirectory(c,remembered[c.kind==='chapter'?'chapter_id':'knowledge_tree_id']);if(String(remembered.phase_id)===String(c.phase_id)&&remembered.grade_id)scope.grade_id=remembered.grade_id;saveDirectoryPreference();}
}
const originalSetTab=setTab;
setTab=function(value){
  if(state)initializeDirectoryPreference();
  if(value==='find'&&tab==='library'&&!directoryCleared){const c=state.catalogs.find(c=>c.id===lf.catalog);if(c)useSavedDirectory(c,lf.node);}
  originalSetTab(value);
};
const originalRenderFind=renderFind;
const scopeMetadata=new Map(),scopeMetadataPending=new Set();
function scopeIdentity(){return `${scope.subject_id||''}-${scope.phase_id||''}`;}
async function loadScopeMetadata(){
  if(!scope.subject_id||!scope.phase_id)return;
  const key=scopeIdentity();
  if(scopeMetadata.has(key)){Object.assign(catalog,scopeMetadata.get(key));return;}
  if(scopeMetadataPending.has(key))return;
  scopeMetadataPending.add(key);
  const selectedScope={subject_id:scope.subject_id,phase_id:scope.phase_id};
  try{
    const [editions,grades]=await Promise.all([api('meta/editions?'+params(selectedScope)),api('meta/grades?'+params({phase_id:selectedScope.phase_id}))]);
    scopeMetadata.set(key,{editions,grades});
    if(scopeIdentity()===key){Object.assign(catalog,{editions,grades});if(tab==='find')render();}
  }catch(e){if(scopeIdentity()===key)say('教材与年级列表暂未加载成功，已保存目录仍可使用。',true);}
  finally{scopeMetadataPending.delete(key);}
}
function matchSavedScope(){
  const c=state.catalogs.find(c=>String(c.subject_id)===String(scope.subject_id)&&String(c.phase_id)===String(scope.phase_id)&&c.kind===filterMode&&(c.kind!=='chapter'||String(c.edition_id)===String(scope.edition_id)));
  savedDirectoryId=c?.id||'';directoryCleared=!c;
  nodes=c?.kind==='knowledge'?c.nodes:[];chapters=c?.kind==='chapter'?c.nodes:[];
  fetchOffset=0;saveDirectoryPreference();return c;
}
renderFind=function(){
  initializeDirectoryPreference();
  const saved=state.catalogs.find(c=>c.id===savedDirectoryId);
  if(savedDirectoryId&&!saved){savedDirectoryId='';directoryCleared=true;scope={};nodes=[];chapters=[];saveDirectoryPreference();}
  if(scopeMetadata.has(scopeIdentity()))Object.assign(catalog,scopeMetadata.get(scopeIdentity()));
  originalRenderFind();
  if(source!=='online')return;
  const panel=main.querySelector('.filter-panel');
  const basics=document.createElement('div');basics.className='scope-basics';
  $('#subject_id').closest('label').before(basics);
  basics.append($('#phase_id').closest('label'),$('#subject_id').closest('label'));
  if(saved){
    $('#load-tree').hidden=true;$('#load-tree').nextElementSibling.hidden=true;
    const hint=document.createElement('p');hint.className='scope-cache-hint';
    hint.textContent='已使用本机目录 · 无需重复下载';$('#load-tree').before(hint);
  }
  // Keep basic scope and both search modes visible even when a local tree is reused.
  for(const id of ['subject_id','phase_id'])$('#'+id).onchange=e=>{
    scope={subject_id:scope.subject_id,phase_id:scope.phase_id,[id]:e.target.value};
    catalog.editions=[];catalog.grades=[];matchSavedScope();render();
  };
  main.querySelectorAll('[data-filter-mode]').forEach(b=>b.onclick=()=>{
    filterMode=b.dataset.filterMode;scope={subject_id:scope.subject_id,phase_id:scope.phase_id};
    const cached=state.catalogs.find(c=>String(c.subject_id)===String(scope.subject_id)&&String(c.phase_id)===String(scope.phase_id)&&c.kind===filterMode);
    if(cached)useSavedDirectory(cached);else matchSavedScope();
    render();
  });
  if($('#edition_id')){
    const localEditions=state.catalogs.filter(c=>c.kind==='chapter'&&String(c.subject_id)===String(scope.subject_id)&&String(c.phase_id)===String(scope.phase_id));
    const rows=[...(catalog.editions||[])];for(const c of localEditions)if(!rows.some(e=>String(e.id)===String(c.edition_id)))rows.push({id:c.edition_id,name:c.label});
    $('#edition_id').innerHTML=option(rows,scope.edition_id,'不限教材');
    const remoteEditionChange=$('#edition_id').onchange;
    $('#edition_id').onchange=async e=>{
      scope.edition_id=e.target.value;delete scope.chapter_id;delete scope.knowledge_tree_id;
      if(matchSavedScope()||!e.target.value){render();return;}
      if(!state.connected){render();say('这个教材尚未保存，请连接题庄后加载章节。');return;}
      await remoteEditionChange();
      matchSavedScope();render();
    };
    $('#load-tree').onclick=async()=>{if(!state.connected)return openConnection();await remoteEditionChange();matchSavedScope();render();};
  }
  if(filterMode==='chapter'){$('#load-tree').hidden=!!saved||!scope.edition_id;$('#load-tree').textContent='加载章节目录';$('#load-tree').nextElementSibling.hidden=true;}
  else $('#load-tree').textContent='加载知识点目录';
  if($('#chapter_id'))$('#chapter_id').closest('label').before($('#grade_id').closest('label'));
  const note=document.createElement('p');note.className='scope-choice-hint';note.textContent='知识点和章节二选一，也可以都不限。';$('#fetch-count').closest('label').before(note);
  if(scopeMetadata.has(scopeIdentity())){
    const data=scopeMetadata.get(scopeIdentity());
    // Metadata belongs to the selected scope; never retain another subject's versions.
    Object.assign(catalog,data);$('#grade_id').innerHTML=option(data.grades,scope.grade_id,'全部');
  }else loadScopeMetadata();
  for(const id of ['grade_id','knowledge_tree_id','chapter_id'])if($('#'+id)){
    const existing=$('#'+id).onchange;$('#'+id).onchange=async e=>{await existing?.(e);saveDirectoryPreference();};
  }
  for(const [id,rows,label] of [['knowledge_tree_id',nodes,'知识点'],['chapter_id',chapters,'章节']])if($('#'+id)){
    const select=$('#'+id),field=select.closest('label');field.hidden=true;
    const current=rows.find(n=>String(n.id)===String(scope[id]));
    const model=directoryPickerModel(rows),box=document.createElement('div');box.className='field';
    box.innerHTML=`${label}（可选）<button class="scope-tree-trigger" id="pick-${id}" aria-haspopup="dialog"><span>${esc(current?model.path(current.id):'不限'+label)}</span><span aria-hidden="true">▾</span></button>`;
    field.after(box);$('#pick-'+id).onclick=()=>openDirectoryPicker(id,rows,label);
  }
};
function directoryPickerModel(rows){
  const items=rows.map(n=>({...n,id:String(n.id),parent_id:n.parent_id?String(n.parent_id):''}));
  const byId=new Map(items.map(n=>[n.id,n])),children=new Map();
  for(const n of items){const parent=byId.has(n.parent_id)?n.parent_id:'';if(!children.has(parent))children.set(parent,[]);children.get(parent).push(n);}
  const path=id=>{const trail=[],seen=new Set();for(let n=byId.get(String(id));n&&!seen.has(n.id)&&trail.length<60;n=byId.get(n.parent_id)){seen.add(n.id);trail.unshift(n.name);}return trail.join(' / ');};
  const search=query=>{const terms=query.trim().toLowerCase().split(/\s+/).filter(Boolean);return items.filter(n=>terms.every(t=>path(n.id).toLowerCase().includes(t)));};
  return {items,byId,children,path,search};
}
function openDirectoryPicker(field,rows,label){
  const model=directoryPickerModel(rows),current=String(scope[field]||''),expanded=new Set();
  for(let n=model.byId.get(current),guard=0;n&&guard<60;guard++,n=model.byId.get(n.parent_id))expanded.add(n.parent_id);
  showDialog('选择'+label,`<div class="picker-search-row"><input id="directory-search" class="search" aria-label="搜索${label}" placeholder="输入名称搜索，例如：反比例函数"><button class="secondary" id="directory-unlimited">不限${label}</button></div><p id="directory-count" class="tiny" role="status"></p><div id="directory-results" class="directory-picker"></div><p class="tiny">点箭头展开目录，点名称选择。搜索结果会显示完整路径。</p>`);
  const choose=id=>{scope[field]=id;delete scope[field==='chapter_id'?'knowledge_tree_id':'chapter_id'];fetchOffset=0;saveDirectoryPreference();$('#library-dialog').close();render();};
  $('#directory-unlimited').onclick=()=>choose('');
  const pickButton=n=>`<button class="picker-choice ${n.id===current?'chosen':''}" data-pick-node="${esc(n.id)}" aria-pressed="${n.id===current}"><span>${esc(n.name)}</span>${n.id===current?'<small>已选</small>':''}</button>`;
  const branch=(parent,depth=0)=>depth>60?'':(model.children.get(parent)||[]).map(n=>{
    const has=model.children.has(n.id),open=expanded.has(n.id);
    return `<div class="picker-branch"><div class="picker-row">${has?`<button class="picker-expand" data-expand-node="${esc(n.id)}" aria-label="${open?'收起':'展开'}${esc(n.name)}" aria-expanded="${open}">${open?'▾':'▸'}</button>`:'<span class="picker-indent"></span>'}${pickButton(n)}</div>${has?`<div class="picker-children" ${open?'':'hidden'}>${branch(n.id,depth+1)}</div>`:''}</div>`;
  }).join('');
  const paint=()=>{
    const term=$('#directory-search').value.trim(),matches=term?model.search(term):[];
    $('#directory-count').textContent=term?`找到 ${matches.length} 项${matches.length>100?'，显示前 100 项，可继续输入缩小范围':''}`:`共 ${model.items.length} 项，可逐层展开`;
    $('#directory-results').innerHTML=term?(matches.slice(0,100).map(n=>`<button class="picker-result ${n.id===current?'chosen':''}" data-pick-node="${esc(n.id)}"><strong>${esc(n.name)}</strong><small>${esc(model.path(n.id))}</small></button>`).join('')||'<p class="muted">没有找到，换个关键词试试。</p>'):(branch('')||`<p class="muted">还没有加载${label}目录。请先选择${field==='chapter_id'?'教材版本并加载章节':'学科学段并加载知识点'}；也可以不限${label}取题。</p>`);
    $('#directory-results').querySelectorAll('[data-pick-node]').forEach(b=>b.onclick=()=>choose(b.dataset.pickNode));
    $('#directory-results').querySelectorAll('[data-expand-node]').forEach(b=>b.onclick=()=>{const id=b.dataset.expandNode;expanded.has(id)?expanded.delete(id):expanded.add(id);paint();$('#directory-results').querySelector(`[data-expand-node="${id}"]`)?.focus();});
  };
  $('#directory-search').oninput=paint;paint();$('#directory-search').focus();
}
source='online';
const PAGE_SIZE=20;
const initialHash=location.hash.slice(1);
tab=['home','find','library','basket','pdf','exports','manage'].includes(initialHash)?initialHash:'library';
const oldRender=render;
render=function(){head();if(['home','library','pdf','manage'].includes(tab)){({home:renderHome,library:renderLibrary,pdf:renderPDF,manage:renderManage})[tab]();setBusy();}else{oldRender();if(tab==='basket')addReviewHint();if(tab==='exports')addPrintLinks();if(tab==='find'&&source==='online'&&!catalog.subjects&&!initialCatalogRequested){initialCatalogRequested=true;loadInitial();}}};
function showDialog(title,body){$('#library-dialog-title').textContent=title;$('#library-dialog-body').innerHTML=body;$('#library-dialog-message').textContent='';$('#library-dialog').showModal();}
$('#close-library').onclick=()=>$('#library-dialog').close();
function dialogError(e){$('#library-dialog-message').textContent=e.message;}
async function lib(action,extra={}){if(busy)return null;busy=true;setBusy();try{const result=await api('library',{action,...extra,revision:state.revision,request_id:crypto.randomUUID(),actor:'界面'});await refresh(true);return result;}catch(e){say(e.message,true);await refresh(true);throw e;}finally{busy=false;setBusy();}}
const hashes=ids=>Object.fromEntries(state.questions.filter(q=>ids.includes(q.id)).map(q=>[q.id,q.content_sha256]));
function localScopeLists(){
const subjects=new Map([[2,'数学']]);
for(const row of catalog.subjects||[])subjects.set(Number(row.id),row.name);
for(const row of [...(state.catalogs||[]),...(state.questions||[]),...(state.pdf_batches||[])]){
const id=Number(row.subject_id);if(id&&!subjects.has(id))subjects.set(id,'学科 '+id);
}
return {subjects:[...subjects].map(([id,name])=>({id,name})),phases:[{id:1,name:'小学'},{id:2,name:'初中'},{id:3,name:'高中'}]};
}
function scopeFields(prefix){const local=localScopeLists();return `<div class="form-row"><label class="field">学科<select id="${prefix}-subject" required>${option(local.subjects,scope.subject_id||2,'选择学科')}</select></label><label class="field">学段<select id="${prefix}-phase" required>${option(local.phases,scope.phase_id||2,'选择学段')}</select></label></div><p id="${prefix}-scope-note" class="tiny" role="status"></p>`;}
async function hydrateScope(prefix){
const subj=$('#'+prefix+'-subject'),phase=$('#'+prefix+'-phase'),note=$('#'+prefix+'-scope-note');
const results=await Promise.allSettled([api('meta/subjects'),api('meta/phases')]);
// Ignore requests belonging to a previous render; preserve selections made while loading.
if($('#'+prefix+'-subject')!==subj||$('#'+prefix+'-phase')!==phase)return;
for(const [i,el,key] of [[0,subj,'subjects'],[1,phase,'phases']]){
const r=results[i];if(r.status==='fulfilled'&&Array.isArray(r.value)&&r.value.length){
catalog[key]=r.value;const known=new Set(r.value.map(n=>String(n.id)));
const rows=[...r.value,...localScopeLists()[key].filter(n=>!known.has(String(n.id)))];
el.innerHTML=option(rows,el.value,i?'选择学段':'选择学科');
}}
if(note)note.textContent=results.some(r=>r.status==='rejected')?'学科学段列表暂时无法刷新，已使用本机选项；这不代表目录未开通，PDF 导入不占目录名额。':'';
}
function knowledgeLabels(q){return state.catalogs.filter(c=>c.kind==='knowledge'&&c.subject_id===q.subject_id&&c.phase_id===q.phase_id).flatMap(c=>c.nodes.filter(n=>q.knowledge_tree_ids.includes(n.id)).map(n=>n.name));}
const scopeName=q=>`${q.phase_id===2?'初中':q.phase_id===1?'小学':q.phase_id===3?'高中':'学段 '+q.phase_id} · ${q.subject_id===2?'数学':'学科 '+q.subject_id}`;
function promptAgent(text){$('#agent-prompt').value=`使用 tizhuang-studio，继续工作区 ${JSON.stringify(state.workspace)}。先读 references/library-workflow.md，读取当前 state 和 revision，所有写入通过本工作台服务。`+text;$('#copy-message').textContent='';$('#agent-dialog').showModal();}
function pageTitle(title,description,tools=''){return `<div class="section-title"><div><h1>${title}</h1><p>${description}</p></div><div class="lib-actions">${tools}</div></div>`;}
function bindNav(){main.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>setTab(b.dataset.go));}
function renderHome(){const st=state.library_stats;const recent=state.questions.filter(q=>!q.archived).slice(0,5);main.innerHTML=pageTitle('好题，都在这里。','按知识点找题，把每次备课的积累留在自己的电脑。')+`<div class="home-actions"><button class="hero-action dark" data-go="find"><small>从题庄获取真实题目</small><strong>找几道好题 <span>↗</span></strong></button><button class="hero-action" data-go="pdf"><small>把手头试卷整理入库</small><strong>导入一份 PDF <span>↗</span></strong></button><button class="hero-action" data-go="basket"><small>页面与 Agent 共用组卷篮</small><strong>组一张试卷 <span>↗</span></strong></button></div><div class="stat-grid">${[['全部题目',st.total,'library'],['待核对',st.draft,'review'],['待分知识点',st.unclassified,'unclassified'],['已生成试卷',st.papers,'exports']].map(([label,n,go])=>`<button class="stat" data-stat="${go}"><strong>${n}</strong><span>${label}</span></button>`).join('')}</div><section class="lib-panel compact-catalog"><div><h3>我的目录</h3><p>${state.catalogs.length?state.catalogs.map(c=>`<button class="small-chip" data-open-catalog="${esc(c.id)}">${esc(c.label)} · ${c.nodes.length} 节点</button>`).join(''):'还没有下载知识树，先选择自己的学科学段。'}</p></div><button class="secondary" id="home-catalog">下载目录</button></section><div class="home-columns"><section class="lib-panel"><h3>最近入库</h3>${recent.map(q=>`<button class="recent-question" data-open-q="${esc(q.id)}"><span>${q.content.includes('<img')?'[图] ':''}${esc(q.title||plain(q.content).slice(0,65))}</span><small>${q.status==='reviewed'?'已核对':'待核对'}</small></button>`).join('')||'<p class="muted">第一批题可以从网站取回，也可以导入 PDF。</p>'}<button class="quiet" data-go="library">查看全部 →</button></section><section class="lib-panel"><h3>导入进度</h3>${state.pdf_batches.slice(0,4).map(b=>`<button class="recent-question" data-batch="${esc(b.id)}"><span>${esc(b.filename)}</span><small>${b.question_ids.length?'已入库 '+b.question_ids.length+' 题':'原页已就绪，待 Agent 分题'}</small></button>`).join('')||'<p class="muted">暂无 PDF 导入任务。</p>'}<p class="tiny">题目、目录、组卷篮和历史稿保存在本机。换电脑前，可在“备份迁移”下载完整备份。</p></section></div>`;
bindNav();$('#home-catalog').onclick=openCatalog;main.querySelectorAll('[data-stat]').forEach(b=>b.onclick=()=>{lf.status=b.dataset.stat==='review'?'draft':b.dataset.stat==='unclassified'?'unclassified':'';lf.page=0;setTab(['review','unclassified'].includes(b.dataset.stat)?'library':b.dataset.stat);});main.querySelectorAll('[data-open-catalog]').forEach(b=>b.onclick=()=>{lf.catalog=b.dataset.openCatalog;lf.node='';setTab('library');});main.querySelectorAll('[data-open-q]').forEach(b=>b.onclick=()=>openQuestion(b.dataset.openQ));main.querySelectorAll('[data-batch]').forEach(b=>b.onclick=()=>{pdfSelection=b.dataset.batch;setTab('pdf');});}
function catalogTree(c){const children=new Map(),parents=new Map(c.nodes.map(n=>[n.id,n.parent_id])),counts=new Map();for(const n of c.nodes){const p=n.parent_id||'';if(!children.has(p))children.set(p,[]);children.get(p).push(n);}for(const q of state.questions.filter(q=>!q.archived&&q.subject_id===c.subject_id&&q.phase_id===c.phase_id&&(c.kind!=='chapter'||q.edition_id===c.edition_id))){const seen=new Set();for(let id of q[c.kind==='knowledge'?'knowledge_tree_ids':'chapter_ids']){while(id&&!seen.has(id)){seen.add(id);id=parents.get(id);}}for(const id of seen)counts.set(id,(counts.get(id)||0)+1);}
function branch(parent){return(children.get(parent)||[]).map(n=>{const has=children.has(n.id),button=`<button class="tree-node ${lf.node===n.id?'chosen':''}" data-node="${esc(n.id)}"><span>${esc(n.name)}</span><small>${counts.get(n.id)||0}</small></button>`;return has?`<details ${lf.node===n.id||isAncestor(n.id,lf.node,parents)?'open':''}><summary>${button}</summary><div class="tree-children">${branch(n.id)}</div></details>`:button;}).join('');}return `<div class="knowledge-tree">${branch('')}</div>`;}
function isAncestor(parent,id,parents){for(let guard=0;id&&guard<65;guard++,id=parents.get(id)){if(id===parent)return true;}return false;}
function filteredQuestions(){const c=state.catalogs.find(c=>c.id===lf.catalog),parents=new Map((c?.nodes||[]).map(n=>[n.id,n.parent_id]));const used=new Set(state.exports.flatMap(e=>e.question_ids||[]));return state.questions.filter(q=>!!q.archived===lf.archived&&(!lf.query||(plain(q.content)+' '+q.title+' '+q.knowledge+' '+q.tags.join(' ')).toLowerCase().includes(lf.query.toLowerCase()))&&(!lf.subject||`${q.subject_id}-${q.phase_id}`===lf.subject)&&(!lf.type||q.type===lf.type)&&(!lf.tag||q.tags.includes(lf.tag))&&(!lf.unused||!used.has(q.id))&&(!lf.status||(lf.status==='unclassified'?!q.knowledge_tree_ids.length:q.status===lf.status))&&(!c||(q.subject_id===c.subject_id&&q.phase_id===c.phase_id&&(c.kind!=='chapter'||q.edition_id===c.edition_id)&&(!lf.node||q[c.kind==='knowledge'?'knowledge_tree_ids':'chapter_ids'].some(id=>isAncestor(lf.node,id,parents))))));}
function renderLibrary(){const rows=filteredQuestions();lf.page=Math.min(lf.page,Math.max(0,Math.ceil(rows.length/PAGE_SIZE)-1));const visible=rows.slice(lf.page*PAGE_SIZE,(lf.page+1)*PAGE_SIZE);const c=state.catalogs.find(c=>c.id===lf.catalog);const tags=[...new Set(state.questions.flatMap(q=>q.tags))].sort();const types=[...new Set(state.questions.map(q=>q.type))];const scopes=[...new Map(state.questions.map(q=>[`${q.subject_id}-${q.phase_id}`,scopeName(q)])).entries()];const chosen=visible.filter(q=>librarySelected.has(q.id)).map(q=>q.id);
main.innerHTML=pageTitle('我的题库','目录、标签和题目都保存在本机。按知识点备课，也能按教材章节查找。',`<button class="secondary" id="new-question">＋ 自编题目</button><button class="secondary" id="auto-classify">自动分类</button>`)+`<div class="library-grid"><aside class="lib-panel tree-panel"><div class="tree-title"><strong>分类浏览</strong><button class="quiet" id="catalog-add" aria-label="下载目录">＋</button></div><select id="lib-catalog" aria-label="选择知识树或教材目录">${option(state.catalogs.map(c=>({id:c.id,name:(c.kind==='knowledge'?'知识点 · ':'章节 · ')+c.label})),lf.catalog,'全部目录')}</select><button class="tree-node ${!lf.node?'chosen':''}" data-node=""><span>${c?'整个目录':'全部题目'}</span></button>${c?catalogTree(c):'<p class="muted">选择或下载知识树、教材目录，展开后点击节点找题。</p>'}<h4>标签</h4><div class="chip-list"><button data-tag="" class="${!lf.tag?'active':''}">全部</button>${tags.map(t=>`<button data-tag="${esc(t)}" class="${lf.tag===t?'active':''}">${esc(t)}</button>`).join('')||'<span class="tiny">可在“分类与标签”添加标签</span>'}</div></aside><section><div class="library-filters"><input class="search" id="lib-query" placeholder="搜索题干、标题或标签…" aria-label="搜索本地题库" value="${esc(lf.query)}"><select id="lib-subject" aria-label="学科学段">${option(scopes.map(([id,name])=>({id,name})),lf.subject,'全部学科学段')}</select><select id="lib-status" aria-label="核对与分类状态">${option([{id:'draft',name:'待核对'},{id:'reviewed',name:'已核对'},{id:'unclassified',name:'待分知识点'}],lf.status,'全部状态')}</select><select id="lib-type" aria-label="题型">${option(types.map(t=>({id:t,name:t})),lf.type,'全部题型')}</select><label><input id="lib-unused" type="checkbox" ${lf.unused?'checked':''}> 未组过卷</label><label><input id="lib-archived" type="checkbox" ${lf.archived?'checked':''}> 已归档</label><button id="lib-reset" class="quiet">清除筛选</button></div><div class="library-toolbar"><label><input type="checkbox" id="lib-select-all" ${visible.length&&chosen.length===visible.length?'checked':''}> 本页 ${visible.length} 题</label><span class="spacer"></span><button class="secondary" id="lib-classify">分类与标签 (${chosen.length})</button><button class="secondary" id="lib-review">核对本页已选 (${chosen.length})</button><button class="primary" id="lib-add">加入组卷篮 (${chosen.length})</button></div><div>${visible.map(q=>`<article class="lib-question ${librarySelected.has(q.id)?'selected':''}"><div class="lib-q-head"><input type="checkbox" aria-label="选择题目 ${esc(q.id)}" data-lib-select="${esc(q.id)}" ${librarySelected.has(q.id)?'checked':''}><span class="small-chip">${esc(q.type)}</span><span class="status-label">${q.status==='reviewed'?'已核对':'待核对'}</span><span class="spacer"></span><button class="quiet" data-q-open="${esc(q.id)}">详情</button></div><div class="tz-preview lib-preview">${q.content}</div><div class="lib-q-foot"><span>${q.tags.map(t=>`#${esc(t)}`).join(' ')} ${q.knowledge_tree_ids.length?'· '+esc(knowledgeLabels(q).slice(0,2).join('、')):'· 待分知识点'}${q.chapter_ids.length?` · ${q.chapter_ids.length} 个章节`:''}</span><div class="lib-q-tools"><button class="quiet" data-q-edit="${esc(q.id)}">编辑</button><button class="quiet" data-q-classify="${esc(q.id)}">分类</button><button class="quiet" data-q-archive="${esc(q.id)}">${q.archived?'取消归档':'归档'}</button></div></div></article>`).join('')||'<div class="empty"><h3>这里还没有题目</h3><p>换个分类看看，或从网站和 PDF 放入第一批题。</p><button class="secondary" data-go="find">网站取题</button> <button class="secondary" data-go="pdf">导入 PDF</button></div>'}</div><div class="library-toolbar"><span>共 ${rows.length} 题 · 第 ${lf.page+1} / ${Math.max(1,Math.ceil(rows.length/PAGE_SIZE))} 页</span><span class="spacer"></span><button id="prev-page" class="quiet">上一页</button><button id="next-page" class="quiet">下一页</button><button id="package-selected" class="secondary">导出本页已选题目包</button></div></section></div>`;
bindNav();$('#catalog-add').onclick=openCatalog;$('#new-question').onclick=()=>editQuestion();$('#auto-classify').onclick=async()=>{try{const r=await lib('auto-classify');if(r)say(`已按唯一同名知识点分类 ${r.classified_ids.length} 题，剩余 ${r.remaining_ids.length} 题需要读题判断。`);if(r?.remaining_ids.length)classificationPrompt(r.remaining_ids);}catch{}};
$('#lib-catalog').onchange=e=>{lf.catalog=e.target.value;lf.node='';lf.page=0;render();};main.querySelectorAll('[data-node]').forEach(b=>b.onclick=e=>{e.preventDefault();lf.node=b.dataset.node;lf.page=0;render();});main.querySelectorAll('[data-tag]').forEach(b=>b.onclick=()=>{lf.tag=b.dataset.tag;lf.page=0;render();});
$('#lib-query').oninput=e=>{lf.query=e.target.value;lf.page=0;const pos=e.target.selectionStart;renderLibrary();$('#lib-query').focus();$('#lib-query').setSelectionRange(pos,pos);};for(const [id,key]of [['lib-status','status'],['lib-type','type'],['lib-subject','subject'],['lib-unused','unused'],['lib-archived','archived']])$('#'+id).onchange=e=>{lf[key]=e.target.type==='checkbox'?e.target.checked:e.target.value;lf.page=0;render();};$('#lib-reset').onclick=()=>{lf={catalog:'',node:'',tag:'',status:'',type:'',query:'',unused:false,archived:false,subject:'',page:0};render();};
$('#lib-select-all').onchange=e=>{visible.forEach(q=>e.target.checked?librarySelected.add(q.id):librarySelected.delete(q.id));render();};main.querySelectorAll('[data-lib-select]').forEach(b=>b.onchange=()=>{b.checked?librarySelected.add(b.dataset.libSelect):librarySelected.delete(b.dataset.libSelect);render();});$('#lib-classify').onclick=()=>classifyQuestions(chosen);$('#lib-review').onclick=()=>reviewQuestions(chosen);$('#lib-add').onclick=async()=>{if(!chosen.length)return say('请先勾选本页题目。');if(await command('add',{ids:chosen}))say(`已把 ${chosen.length} 题加入共享组卷篮。`);};
main.querySelectorAll('[data-q-open]').forEach(b=>b.onclick=()=>openQuestion(b.dataset.qOpen));main.querySelectorAll('[data-q-edit]').forEach(b=>b.onclick=()=>editQuestion(b.dataset.qEdit));main.querySelectorAll('[data-q-classify]').forEach(b=>b.onclick=()=>classifyQuestions([b.dataset.qClassify]));main.querySelectorAll('[data-q-archive]').forEach(b=>b.onclick=()=>{const q=state.questions.find(q=>q.id===b.dataset.qArchive);showDialog(q.archived?'取消归档':'归档题目',`<p>${q.archived?'题目将重新出现在题库。':'题目会从常用列表收起，数据仍保留，可随时取消归档。'}</p><button class="primary" id="confirm-archive">确认</button>`);$('#confirm-archive').onclick=async()=>{try{await lib('archive',{ids:[q.id],hashes:hashes([q.id]),archived:!q.archived,confirm:true});$('#library-dialog').close();}catch(e){dialogError(e);}};});
$('#prev-page').onclick=()=>{if(lf.page){lf.page--;render();}};$('#next-page').onclick=()=>{if((lf.page+1)*PAGE_SIZE<rows.length){lf.page++;render();}};$('#package-selected').onclick=()=>exportPackage(chosen);}
function openQuestion(id){const q=state.questions.find(q=>q.id===id);showDialog(q.title||'题目详情',`<div class="tz-preview">${q.content}<hr><h3>答案</h3>${q.answer||'原题未提供答案'}<h3>解析</h3>${q.analysis||'原题未提供解析'}</div>${q.notes?`<p>笔记：${esc(q.notes)}</p>`:''}${q.source_pdf?`<p>原题号：${esc(q.source_pdf.number)} · ${esc(q.source_pdf.uncertainties.join('；'))}</p><button class="secondary" id="q-origin">查看 PDF 原页</button>`:''}<p class="tiny">${esc(q.source?.label||'')} · ${esc(id)}</p><div class="lib-actions"><button id="detail-edit" class="secondary">编辑题目</button><button id="detail-review" class="primary">${q.status==='reviewed'?'重新核对':'标记为已核对'}</button></div>`);$('#detail-edit').onclick=()=>{$('#library-dialog').close();editQuestion(id);};$('#detail-review').onclick=()=>{$('#library-dialog').close();reviewQuestions([id]);};if($('#q-origin'))$('#q-origin').onclick=()=>{$('#library-dialog').close();pdfSelection=q.source_pdf.batch_id;setTab('pdf');};}
function reviewQuestions(ids){if(!ids.length)return say('请勾选本页要核对的题目。');const expected=hashes(ids);showDialog(`核对 ${ids.length} 道题`,`${ids.map(id=>{const q=state.questions.find(q=>q.id===id);return `<section class="review-question"><div class="tz-preview">${q.content}<h4>原答案与解析</h4>${q.answer||'原题未提供答案'}${q.analysis||''}</div>${q.source_pdf?`<p class="tiny">原题号 ${esc(q.source_pdf.number)} · ${esc(q.source_pdf.uncertainties.join('；'))}</p>`:''}</section>`;}).join('')}<label class="review-confirm"><input id="review-confirm" type="checkbox"> 我已核对以上题目的题干、答案、公式与配图。</label><button id="save-review" class="primary">确认已核对</button>`);$('#save-review').onclick=async()=>{if(!$('#review-confirm').checked)return dialogError(Error('请先逐题核对并勾选确认。'));try{await lib('review',{ids,hashes:expected,confirm:true});$('#library-dialog').close();say(`已标记 ${ids.length} 题为已核对。`);}catch(e){dialogError(e);}};}
function editQuestion(id){const q=state.questions.find(q=>q.id===id);const text=q?.editable||{content:q?.content||'',answer:q?.answer||'',analysis:q?.analysis||'',format:q?'html':'markdown'};const expected=q?hashes([id]):{};showDialog(q?'编辑题目':'自编题目',`<form id="edit-question-form">${!q?scopeFields('edit'):''}<label class="field">简短标题（可选）<input id="edit-title" maxlength="120" value="${esc(q?.title||'')}"></label><div class="form-row"><label class="field">题型<input id="edit-type" value="${esc(q?.type||'解答题')}"></label><label class="field">正文格式<select id="edit-format">${option([{id:'markdown',name:'Markdown + LaTeX'},{id:'html',name:'HTML + MathML'}],text.format,'选择格式')}</select></label></div>${[['content','题干'],['answer','原答案'],['analysis','原解析']].map(([k,n])=>`<label class="field">${n}<textarea id="edit-${k}" rows="${k==='content'?6:3}" ${k==='content'?'required':''}>${esc(text[k]||'')}</textarea></label>`).join('')}<label class="field">教学笔记（不进入试卷）<textarea id="edit-notes" rows="2">${esc(q?.notes||'')}</textarea></label><p class="tiny">保留原有 Assets/ 配图路径。修改后须重新核对；原内容保存在编辑历史中。</p><button class="primary" type="submit">保存为待核对</button></form>`);if(!q)hydrateScope('edit');$('#edit-question-form').onsubmit=async e=>{e.preventDefault();try{await lib(q?'edit':'create',{id,hashes:expected,subject_id:Number($('#edit-subject')?.value),phase_id:Number($('#edit-phase')?.value),title:$('#edit-title').value,type:$('#edit-type').value,format:$('#edit-format').value,text:Object.fromEntries(['content','answer','analysis'].map(k=>[k,$('#edit-'+k).value])),notes:$('#edit-notes').value});$('#library-dialog').close();say('已保存，题目处于待核对状态。');}catch(e){dialogError(e);}};}
function classifyQuestions(ids){if(!ids.length)return say('请先勾选本页题目。');const qs=state.questions.filter(q=>ids.includes(q.id));if(new Set(qs.map(q=>q.subject_id+'-'+q.phase_id)).size>1)return say('请按同一学科学段分批分类。',true);const q=qs[0],cats=state.catalogs.filter(c=>c.subject_id===q.subject_id&&c.phase_id===q.phase_id);const expected=hashes(ids);const common=field=>qs.reduce((all,x)=>all.filter(v=>x[field].includes(v)),q[field]);showDialog(`分类与标签 · ${ids.length} 题`,`<p>本次会将勾选的分类和标签应用到这 ${ids.length} 道题，不改变题干和答案。</p><label class="field">教材目录<select id="class-edition">${option(cats.filter(c=>c.kind==='chapter').map(c=>({id:c.edition_id,name:c.label})),q.edition_id,'不设置教材')}</select></label><label class="field">筛选节点<input id="class-search" placeholder="输入知识点或章节名称"></label><div class="classification-options">${cats.map(c=>`<fieldset data-class-catalog="${esc(c.kind)}" data-edition="${c.edition_id||''}"><legend>${esc(c.label)}</legend>${c.nodes.map(n=>`<label data-class-label="${esc(n.name)}"><input type="checkbox" data-class-kind="${c.kind}" value="${esc(n.id)}" ${common(c.kind==='knowledge'?'knowledge_tree_ids':'chapter_ids').includes(n.id)?'checked':''}> ${esc(n.name)}</label>`).join('')}</fieldset>`).join('')||'<p>还没有本地目录，先在分类浏览旁点 ＋ 下载。</p>'}</div><label class="field">标签（用逗号分隔）<input id="class-tags" value="${esc(common('tags').join('，'))}"></label><div class="lib-actions"><button class="primary" id="save-classification">保存分类</button><button class="secondary" id="agent-classification">让 Agent 读题分类</button></div>`);
const filterOptions=()=>{const ed=$('#class-edition').value,term=$('#class-search').value;$('#library-dialog-body').querySelectorAll('[data-class-catalog]').forEach(f=>{f.hidden=f.dataset.classCatalog==='chapter'&&f.dataset.edition!==ed;f.querySelectorAll('label').forEach(l=>l.hidden=!l.dataset.classLabel.includes(term));});};$('#class-edition').onchange=filterOptions;$('#class-search').oninput=filterOptions;filterOptions();$('#agent-classification').onclick=()=>{$('#library-dialog').close();classificationPrompt(ids);};$('#save-classification').onclick=async()=>{const checked=kind=>[...$('#library-dialog-body').querySelectorAll(`[data-class-kind="${kind}"]:checked`)].filter(x=>!x.closest('fieldset').hidden).map(x=>x.value);try{await lib('classify',{ids,hashes:expected,knowledge_tree_ids:checked('knowledge'),chapter_ids:checked('chapter'),edition_id:$('#class-edition').value?Number($('#class-edition').value):null,tags:$('#class-tags').value.split(/[,，]/).map(t=>t.trim()).filter(Boolean)});$('#library-dialog').close();say('分类已保存。');}catch(e){dialogError(e);}};}
function classificationPrompt(ids){promptAgent(`请对题号 ${JSON.stringify(ids)} 做知识点分类：先 show 逐题阅读正文、答案和配图，查当前 catalogs 真实节点，使用 content_sha256 防止覆盖新修改。暂不选择教材，不猜章节。用 library classify 写入知识点；不确定的保留待分类并说明。不得替老师标记已核对。`);}
async function openCatalog(){showDialog('下载知识树 / 教材目录',`<p>按“学段 × 学科”使用账号目录名额；同范围重复使用不重复占名额。下载后保存在本机。</p><form id="catalog-form"><div class="form-row"><label class="field">学科<select id="catalog-subject" required><option value="">正在加载…</option></select></label><label class="field">学段<select id="catalog-phase" required><option value="">正在加载…</option></select></label></div><label class="field">目录类型<select id="catalog-kind"><option value="knowledge">知识点树</option><option value="chapter">教材章节树</option></select></label><label class="field" id="edition-field" hidden>教材版本<select id="catalog-edition"><option value="">选择教材</option></select></label><label class="field">显示名称<input id="catalog-label" placeholder="例如：初中数学知识点"></label><label class="review-confirm"><input type="checkbox" id="catalog-replace"> 更新同范围已下载目录（保留题目的有效关联）</label><button type="submit" class="primary">下载并保存</button></form><details><summary>由 Agent 提供目录</summary><p class="tiny">Agent 可通过已授权 MCP 读真实目录，再用 library catalog-save 保存，不需要把 OAuth 令牌交给页面。</p><button id="catalog-agent" class="secondary">复制 Agent 指令</button></details>`);
$('#catalog-agent').onclick=()=>{$('#library-dialog').close();promptAgent('请使用已连接的题庄 MCP 或当前工作台 API Key 获取我指定学科学段的真实知识树，使用 library catalog-save 落盘。先核对目录名额；不编造节点，不默认选择教材。');};
const editions=async()=>{const kind=$('#catalog-kind').value;$('#edition-field').hidden=kind!=='chapter';if(kind==='chapter'&&$('#catalog-subject').value&&$('#catalog-phase').value){try{$('#catalog-edition').innerHTML=option(await api('meta/editions?'+params({subject_id:$('#catalog-subject').value,phase_id:$('#catalog-phase').value})),'','选择教材');}catch(e){dialogError(e);}}};for(const id of ['catalog-kind','catalog-subject','catalog-phase'])$('#'+id).onchange=editions;
$('#catalog-form').onsubmit=async e=>{e.preventDefault();const subject=Number($('#catalog-subject').value),phase=Number($('#catalog-phase').value),kind=$('#catalog-kind').value,ed=Number($('#catalog-edition').value);if(!state.connected)return dialogError(Error('页面下载需先连接 API Key；也可使用下方 Agent 目录流程。'));if(kind==='chapter'&&!ed)return dialogError(Error('请选择教材。'));try{await lib('catalog-fetch',{kind,subject_id:subject,phase_id:phase,edition_id:ed,label:$('#catalog-label').value||$('#catalog-phase').selectedOptions[0].textContent+$('#catalog-subject').selectedOptions[0].textContent+(kind==='knowledge'?'知识点':' · '+$('#catalog-edition').selectedOptions[0].textContent),replace:$('#catalog-replace').checked});$('#library-dialog').close();say('目录已保存到本机，可在“我的题库”展开浏览。');}catch(e){dialogError(e);}};
try{const [subjects,phases]=await Promise.all([api('meta/subjects'),api('meta/phases')]);if($('#catalog-subject')){$('#catalog-subject').innerHTML=option(subjects,'','选择学科');$('#catalog-phase').innerHTML=option(phases,'','选择学段');}}catch(e){dialogError(e);}}
async function encodeFile(file,limit){if(!file||file.size>limit)throw Error(`请选择不超过 ${limit/1024/1024} MB 的文件。`);const bytes=new Uint8Array(await file.arrayBuffer());let value='';for(let i=0;i<bytes.length;i+=32768)value+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(value);}
let pdfDirectoryChoice=null;
function pdfScopeChoice(){
const rows=state.catalogs||[];
if(pdfDirectoryChoice==='')return '';
if(rows.some(c=>c.id===pdfDirectoryChoice))return pdfDirectoryChoice;
return rows.find(c=>c.id===savedDirectoryId)?.id||rows.find(c=>String(c.subject_id)===String(scope.subject_id)&&String(c.phase_id)===String(scope.phase_id))?.id||rows[0]?.id||'';
}
let pdfScopeSelection=null;
function pdfScopeFields(){
  const cached=state.catalogs.find(c=>c.id===pdfScopeChoice());
  const chosen=pdfScopeSelection||cached||{subject_id:scope.subject_id||2,phase_id:scope.phase_id||2};
  const local=localScopeLists();
  return `<div class="pdf-scope"><label class="field">学段<select id="pdf-phase" required>${option(local.phases,chosen.phase_id,'选择学段')}</select></label><label class="field">学科<select id="pdf-subject" required>${option(local.subjects,chosen.subject_id,'选择学科')}</select></label></div><p id="pdf-scope-note" class="tiny" role="status"></p><p class="tiny">导入后再分知识点，教材章节选填。</p>`;
}
function bindPDFScope(){
  const remember=()=>{pdfScopeSelection={subject_id:$('#pdf-subject').value,phase_id:$('#pdf-phase').value};};
  for(const id of ['pdf-subject','pdf-phase'])$('#'+id).onchange=remember;
  remember();
  if(state.connected)hydrateScope('pdf');
}
function renderPDF(){const batch=state.pdf_batches.find(b=>b.id===pdfSelection)||state.pdf_batches[0];main.innerHTML=pageTitle('把试卷，变成自己的题库。','先保存 PDF 原页，再让 Agent 识别可编辑题干、原答案和独立配图，最后逐题核对。')+`<div class="pdf-grid"><aside><section class="lib-panel"><h3>导入 PDF</h3><form id="pdf-form"><label class="field">试卷文件<input type="file" id="pdf-file" accept="application/pdf,.pdf" required></label>${pdfScopeFields()}<p class="tiny">每批最多 30 MB、60 页。知识点可以先分类，教材以后再选。</p><button class="primary" type="submit">准备原页</button></form></section><section class="lib-panel"><h3>导入批次</h3>${state.pdf_batches.map(b=>`<button class="batch-button ${batch?.id===b.id?'active':''}" data-pdf-batch="${b.id}"><span>${esc(b.filename)}</span><small>${b.pages.length} 页 · ${b.question_ids.length?'已入库 '+b.question_ids.length+' 题':'待分题'}</small></button>`).join('')||'<p class="muted">上传后会显示在这里。</p>'}</section></aside><section class="lib-panel">${batch?`<div class="section-title"><div><h2>${esc(batch.filename)}</h2><p>${scopeName(batch)} · ${batch.pages.length} 页 · 已入库 ${batch.question_ids.length} 题</p></div><a href="/pdf/${batch.id}/original.pdf">下载原件</a></div><div class="workflow-steps"><span>① 原页已保存</span><span>② Agent 识别分题</span><span>③ 教师核对</span></div><p>整题保持可编辑文字和公式，图片只裁图形；去掉题号与“第几题图”说明，保留数学标注和水印。缺失答案须明确标记，不让 AI 冒充原答案。</p><div class="lib-actions"><button id="pdf-agent" class="primary">交给 Agent 分题</button><label class="file-button secondary">导入分题 JSON<input type="file" id="pdf-plan" accept="application/json,.json"></label><button class="secondary" data-go="library">去核对题目</button></div><p class="tiny">扫描件需 Agent 视觉识别；下方提取文字仅供辅助，必须对照原页。</p><label class="field">查看原页<select id="pdf-page">${batch.pages.map(p=>`<option value="${p.number}">第 ${p.number} 页${p.needs_visual_reading?' · 扫描页':''}</option>`).join('')}</select></label><div id="pdf-page-view"></div>`:'<div class="empty"><h3>先放入一份 PDF</h3><p>原件和页面会保存在本机，关闭页面后也可继续。</p></div>'}</section></div>`;
bindNav();bindPDFScope();$('#pdf-form').onsubmit=async e=>{e.preventDefault();try{const f=$('#pdf-file').files[0];const encoded=await encodeFile(f,30*1024*1024);say('正在保存原页与提取文字，请稍候…');const r=await lib('pdf-prepare',{file_base64:encoded,filename:f.name,subject_id:Number($('#pdf-subject').value),phase_id:Number($('#pdf-phase').value)});if(r){pdfSelection=r.batch_id;render();say(r.existing?'已打开这份 PDF 的原批次。':r.message);}}catch(e){say(e.message,true);}};main.querySelectorAll('[data-pdf-batch]').forEach(b=>b.onclick=()=>{pdfSelection=b.dataset.pdfBatch;render();});if(batch){const page=()=>{const p=batch.pages[Number($('#pdf-page').value)-1];$('#pdf-page-view').innerHTML=`<a href="/pdf/${batch.id}/${p.image}" target="_blank" rel="noopener"><img class="pdf-original" src="/pdf/${batch.id}/${p.image}" alt="PDF 第 ${p.number} 页原图"></a><details><summary>查看提取文字</summary><pre>${esc(p.text||'扫描页暂无文字层，请对照原图识别。')}</pre></details>`;};$('#pdf-page').onchange=page;page();$('#pdf-agent').onclick=()=>promptAgent(`继续 PDF 批次 ${batch.id}，先使用 pdf-batch 读取批次路径，逐页查看 PNG 原页，按 references/pdf-workflow.md 的 v2 清单还原可编辑题干、LaTeX、原答案及独立配图，去掉外层原题号及图片中的题号说明，保留数学标注和水印。不要把整题截图入库，不猜原答案。使用 library pdf-import 保存为待核对，匹配真实知识点；不默认选择教材。`);$('#pdf-plan').onchange=async e=>{try{const f=e.target.files[0];if(!f||f.size>2*1024*1024)throw Error('分题清单须小于 2 MB。');const plan=JSON.parse(await f.text());const r=await lib('pdf-import',{batch_id:batch.id,plan});if(r)say(`已入库 ${r.imported_ids.length} 题，跳过重复 ${r.existing_ids.length} 题。请到我的题库核对。`);}catch(e){say(e.message,true);}};}}
async function exportPackage(ids){if(!ids.length)return say('请先勾选本页题目。');showDialog('导出题目包',`<p>导出 ${ids.length} 道题和本地配图，用于其他工作台或后续迁移。</p><label class="review-confirm"><input type="checkbox" id="package-answers" checked> 包含原答案与解析</label><button class="primary" id="package-export">生成 ZIP</button>`);$('#package-export').onclick=async()=>{try{const r=await lib('package-export',{ids,include_solutions:$('#package-answers').checked});if(r)$('#library-dialog-body').innerHTML=`<p>题目包已生成。</p><a class="primary download-button" href="${esc(r.url)}">下载题目包 ↓</a>`;}catch(e){dialogError(e);}};}
function renderManage(){main.innerHTML=pageTitle('留好备份，安心积累。','完整备份包含题目、目录、PDF 原件、组卷篮与历史试卷。不会包含 API Key 或工作台会话凭据。')+`<div class="home-columns"><section class="lib-panel"><h3>完整工作台备份</h3><p>换电脑或重要整理前，下载一份 ZIP。题目包适合只带走选中的题。</p><button class="primary" id="make-backup">创建完整备份</button><p class="tiny">恢复会替换当前工作台状态，并先自动保存恢复前备份。</p><label class="file-button secondary">选择备份并恢复<input type="file" id="restore-file" accept=".zip"></label></section><section class="lib-panel"><h3>题目包迁移</h3><p>导入题目和配图，同题号自动跳过；已有题目与组卷篮保持原样。导入题目先标为待核对。</p><label class="file-button secondary">导入题目包 ZIP<input type="file" id="import-package-file" accept=".zip"></label><p class="tiny">支持本工作台和本地题库导出的 v1 题目包。未带目录快照的知识编号会保留为待映射，不猜分类。</p><button class="quiet" data-go="library">去我的题库选题导出 →</button></section></div><section class="lib-panel"><div class="tree-title"><h3>已生成的备份与题目包</h3><button id="reload-backups" class="quiet">刷新</button></div><div id="backup-list">正在读取…</div></section>`;bindNav();const load=async()=>{try{backups=await api('backups');if($('#backup-list'))$('#backup-list').innerHTML=backups.map(b=>`<div class="backup-row"><span>${esc(b.id)} · ${(b.size/1024/1024).toFixed(1)} MB</span><a href="${esc(b.url)}">下载 ZIP ↓</a></div>`).join('')||'<p class="muted">还没有备份。</p>';}catch(e){say(e.message,true);}};$('#reload-backups').onclick=load;load();$('#make-backup').onclick=async()=>{try{const r=await lib('backup');if(r)say(`备份已生成，共 ${r.count} 道题。请下载并妥善保管。`);}catch{}};
for(const [id,action]of [['restore-file','restore'],['import-package-file','package-import']])$('#'+id).onchange=async e=>{const f=e.target.files[0];if(!f)return;showDialog(action==='restore'?'确认恢复工作台':'导入题目包',`<p>${esc(f.name)}</p><p>${action==='restore'?'本次将替换当前题目、目录、组卷篮和试卷记录。恢复前会自动备份当前工作台。':'新增题目先标为待核对，同题号跳过。'}</p><button class="primary" id="confirm-import">${action==='restore'?'确认恢复':'确认导入'}</button>`);$('#confirm-import').onclick=async()=>{try{const file_base64=await encodeFile(f,250*1024*1024);const r=await lib(action,{file_base64,confirm:true});if(r){$('#library-dialog').close();librarySelected.clear();selected.clear();say(`已完成，导入 ${r.imported_ids.length} 道题。`);}}catch(e){dialogError(e);}};};}
function addReviewHint(){const ids=state.items.map(i=>i.id).filter(id=>state.questions.find(q=>q.id===id)?.status!=='reviewed');if(!ids.length)return;const box=document.createElement('div');box.className='review-hint';box.innerHTML=`<p>本卷有 ${ids.length} 道待核对题。导出前请核对题干、答案和图片。</p><button id="basket-review" class="secondary">逐题查看并核对</button>`;$('#export').before(box);$('#basket-review').onclick=()=>reviewQuestions(ids);}
function addPrintLinks(){main.querySelectorAll('.export-row').forEach((row,i)=>{if(row.querySelector('.print-links'))return;const e=state.exports[i];if(e.student_html){const box=document.createElement('div');box.className='print-links';box.innerHTML=`<a href="${esc(e.student_html)}" target="_blank" rel="noopener">无答案打印稿 ↗</a><a href="${esc(e.teacher_html)}" target="_blank" rel="noopener">教师打印稿 ↗</a>`;row.append(box);}});}
window.addEventListener('hashchange',()=>{const value=location.hash.slice(1);if(['home','find','library','basket','pdf','exports','manage'].includes(value)){tab=value;if(state)render();}});
