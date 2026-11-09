'use strict';
// Presentation only. The existing service remains the sole owner of questions and papers.
function scopeCatalogs(rows,phase,subject,kind){return rows.filter(c=>(!phase||String(c.phase_id)===String(phase))&&(!subject||String(c.subject_id)===String(subject))&&(!kind||c.kind===kind));}
function workflowStep(route){return ['find','pdf','library'].includes(route)?'library':route;}
let browseScope=null,treeQuery='',quotaRequested=false;
const browseKey=()=>`tizhuang:browse-scope:${state.workspace}`;
function initBrowseScope(){
  if(browseScope)return;
  let saved;try{saved=JSON.parse(localStorage.getItem(browseKey())||'null');}catch{}
  const c=state.catalogs.find(c=>c.id===lf.catalog),[subject,phase]=(lf.subject||'').split('-');
  browseScope=saved&&typeof saved==='object'?{phase:String(saved.phase||''),subject:String(saved.subject||''),kind:saved.kind==='chapter'?'chapter':'knowledge',edition:String(saved.edition||'')}:{phase:String(c?.phase_id||phase||''),subject:String(c?.subject_id||subject||''),kind:c?.kind||'knowledge',edition:String(c?.edition_id||'')};
}
function rememberBrowse(){try{localStorage.setItem(browseKey(),JSON.stringify(browseScope));}catch{}}
function syncBrowseCatalog(){
  const b=browseScope;
  const rows=b.phase&&b.subject?scopeCatalogs(state.catalogs,b.phase,b.subject,b.kind):[];
  const c=b.kind==='chapter'?rows.find(c=>String(c.edition_id)===b.edition):rows[0];
  if(lf.catalog!==(c?.id||''))lf.node='';
  lf.catalog=c?.id||'';lf.subject='';
  return c;
}
function phaseButtons(select,all=false){
  const box=document.createElement('div');box.className='phase-buttons';box.setAttribute('role','group');box.setAttribute('aria-label','选择学段');
  const rows=[...(all?[{id:'',name:'全部'}]:[]),...localScopeLists().phases];
  const paint=()=>{box.innerHTML=rows.map(n=>`<button type="button" data-phase="${n.id}" aria-pressed="${String(n.id)===select.value}">${esc(n.name)}</button>`).join('');box.querySelectorAll('button').forEach(b=>b.onclick=()=>{select.value=b.dataset.phase;select.dispatchEvent(new Event('change',{bubbles:true}));if(box.isConnected)paint();});};
  select.hidden=true;select.after(box);paint();
}
const compactHead=head;
head=function(){
  compactHead();
  const current=workflowStep(tab);
  document.querySelectorAll('[data-tab]').forEach(b=>{const active=b.dataset.tab===current;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  const remaining=quota?Math.min(quota.remaining,quota.member_remaining??quota.remaining):null;
  $('#connect').textContent=state.connected?`● 已连接${remaining==null?' · 查看额度':` · 可用 ${remaining} 题`}`:'连接题庄';
  $('#connect').classList.toggle('connected',!!state.connected);
  if(!state.connected){quotaRequested=false;quota=null;}
  else if(!quotaRequested){quotaRequested=true;api('quota').then(q=>{quota=q;head();}).catch(()=>{quota=null;$('#connect').textContent='● 已连接 · 额度暂不可用';});}
};
const compactSetTab=setTab;
setTab=function(value){
  if(value!==tab)say('');
  if(tab==='library'&&['find','pdf'].includes(value)&&browseScope?.phase&&browseScope?.subject){
    scope={phase_id:browseScope.phase,subject_id:browseScope.subject};filterMode=browseScope.kind;
    const c=state.catalogs.find(c=>c.id===lf.catalog);if(c)useSavedDirectory(c,lf.node);else matchSavedScope();
    pdfScopeSelection={phase_id:scope.phase_id,subject_id:scope.subject_id};
  }
  if(value==='find')source='online';compactSetTab(value);
};
const compactFilter=filteredQuestions;
filteredQuestions=function(){return compactFilter().filter(q=>!browseScope||((!browseScope.phase||String(q.phase_id)===browseScope.phase)&&(!browseScope.subject||String(q.subject_id)===browseScope.subject)));};

const compactLibrary=renderLibrary;
renderLibrary=function(){
  restorePreferences();initBrowseScope();const c=syncBrowseCatalog();
  compactLibrary();
  main.querySelector('h1').textContent='我的题目';
  main.querySelector('.section-title p').textContent=`${state.library_stats.total} 题 · ${state.library_stats.draft} 待核对`;
  const tools=main.querySelector('.section-title .lib-actions');
  const create=$('#new-question');create.hidden=true;
  const add=document.createElement('div');add.className='add-question-actions';add.setAttribute('aria-label','添加题目');
  add.innerHTML='<button type="button" class="primary" data-add="find">＋ 网站取题</button><button type="button" class="secondary" data-add="pdf">导入 PDF</button><button type="button" class="secondary" data-add="create">自编题目</button>';
  tools.append(add);add.querySelectorAll('button').forEach(b=>b.onclick=()=>b.dataset.add==='create'?editQuestion():setTab(b.dataset.add));
  const summary=document.createElement('div');summary.className='library-shortcuts';
  summary.innerHTML='<span>放入第一批题或继续积累</span><button class="quiet" data-go="find">网站取题 ↗</button><button class="quiet" data-go="pdf">导入 PDF ↗</button>';
  if(!state.questions.length)main.querySelector('.section-title').after(summary);
  const old=$('#lib-catalog');old.hidden=true;
  const box=document.createElement('div');box.className='browse-scope';
  const b=browseScope,local=localScopeLists(),editions=b.phase&&b.subject?scopeCatalogs(state.catalogs,b.phase,b.subject,'chapter'):[];
  box.innerHTML=`<label class="field">学段<select id="browse-phase" aria-label="浏览学段">${option(local.phases,b.phase,'全部学段')}</select></label><label class="field">学科<select id="browse-subject">${option(local.subjects,b.subject,'全部学科')}</select></label><div class="source-switch browse-modes" role="group" aria-label="分类方式"><button data-browse-mode="knowledge" aria-pressed="${b.kind==='knowledge'}" class="${b.kind==='knowledge'?'active':''}">知识点</button><button data-browse-mode="chapter" aria-pressed="${b.kind==='chapter'}" class="${b.kind==='chapter'?'active':''}">教材章节</button></div>${b.kind==='chapter'?`<label class="field">教材版本<select id="browse-edition">${option(editions.map(c=>({id:c.edition_id,name:c.label})),b.edition,'选择已下载教材')}</select></label>`:''}<input id="browse-tree-search" class="search" aria-label="搜索目录节点" placeholder="搜索${b.kind==='chapter'?'章节':'知识点'}…" value="${esc(treeQuery)}" ${c?'':'hidden'}>`;
  old.after(box);phaseButtons($('#browse-phase'),true);$('#lib-subject').hidden=true;
  const change=(key,value)=>{b[key]=value;if(key!=='edition')b.edition='';lf.node='';lf.page=0;treeQuery='';rememberBrowse();render();};
  $('#browse-phase').onchange=e=>change('phase',e.target.value);
  $('#browse-subject').onchange=e=>change('subject',e.target.value);
  box.querySelectorAll('[data-browse-mode]').forEach(el=>el.onclick=()=>change('kind',el.dataset.browseMode));
  if($('#browse-edition'))$('#browse-edition').onchange=e=>change('edition',e.target.value);
  const tree=main.querySelector('.knowledge-tree');
  if(c&&tree){
    const original=tree.innerHTML,model=directoryPickerModel(c.nodes);
    const paint=()=>{const term=$('#browse-tree-search').value.trim();treeQuery=term;
      tree.innerHTML=term?model.search(term).slice(0,100).map(n=>`<button class="tree-search-result" data-node="${esc(n.id)}"><strong>${esc(n.name)}</strong><small>${esc(model.path(n.id))}</small></button>`).join('')||'<p class="tiny">没有匹配的节点</p>':original;
      tree.querySelectorAll('[data-node]').forEach(el=>el.onclick=e=>{e.preventDefault();lf.node=el.dataset.node;lf.page=0;render();});
    };$('#browse-tree-search').oninput=paint;if(treeQuery)paint();
  }
  if(!c){const hint=main.querySelector('.tree-panel > .muted');if(hint){hint.innerHTML=b.phase&&b.subject?(b.kind==='chapter'&&editions.length?'请选择一本已下载教材，或下载其他版本。':'这个范围的'+(b.kind==='chapter'?'教材目录':'知识点树')+'尚未下载，题目仍可查看。'):'先选择学段和学科，再展开知识点或章节。';if(b.phase&&b.subject){const btn=document.createElement('button');btn.className='secondary';btn.textContent='下载'+(b.kind==='chapter'?'教材目录':'知识点树');btn.onclick=openScopedCatalog;hint.append(document.createElement('br'),btn);}}}
  $('#catalog-add').onclick=openScopedCatalog;
  $('#lib-reset').onclick=()=>{browseScope={phase:'',subject:'',kind:'knowledge',edition:''};treeQuery='';lf=cleanPreferences({}).library;rememberBrowse();render();};
  bindNav();rememberBrowse();
};
async function openScopedCatalog(){
  await openCatalog();
  if(!$('#catalog-phase'))return;
  $('#catalog-phase').value=browseScope?.phase||'';$('#catalog-subject').value=browseScope?.subject||'';
  $('#catalog-kind').value=browseScope?.kind||'knowledge';
  $('#catalog-kind').dispatchEvent(new Event('change'));
  const row=$('#catalog-phase').closest('.form-row');row.prepend($('#catalog-phase').closest('label'));
}
function acquisitionNav(){
  const nav=document.createElement('nav');nav.className='acquisition-nav';nav.setAttribute('aria-label','添加题目');
  nav.innerHTML=`<button class="quiet" data-go="library">← 我的题目</button><span class="nav-divider"></span><button data-go="find" class="${tab==='find'?'active':''}">网站取题</button><button data-go="pdf" class="${tab==='pdf'?'active':''}">导入 PDF</button>`;
  main.prepend(nav);bindNav();
}
const compactFind=renderFind;
renderFind=function(){
  const local=localScopeLists();if(!catalog.subjects?.length)catalog.subjects=local.subjects;if(!catalog.phases?.length)catalog.phases=local.phases;
  source='online';compactFind();acquisitionNav();
  const sourceNav=main.querySelector('.filter-panel > .source-switch');if(sourceNav)sourceNav.hidden=true;
  const basics=main.querySelector('.scope-basics');if(basics)basics.classList.add('unified-scope');
  if($('#phase_id'))phaseButtons($('#phase_id'));
  main.querySelector('.section-title h1').textContent='网站取题';
  main.querySelector('.section-title p')?.remove();
  if(state.connected&&!initialCatalogRequested){initialCatalogRequested=true;loadInitial();}
};
const compactPDF=renderPDF;
renderPDF=function(){compactPDF();main.querySelector('.section-title p')?.remove();acquisitionNav();phaseButtons($('#pdf-phase'));};
const compactHome=renderHome;
renderHome=function(){compactHome();main.querySelector('h1').textContent='概览';main.querySelector('.section-title p')?.remove();};

function setTheme(theme){
  document.documentElement.dataset.theme=theme;
  document.querySelector('.brand img').src=theme==='dark'?'/web/logo-dark.svg':'/web/logo.svg';
  $('#theme-toggle').textContent=theme==='dark'?'☀ 浅色':'☾ 深色';
  $('#theme-toggle').setAttribute('aria-label',theme==='dark'?'切换浅色模式':'切换深色模式');
  $('#theme-toggle').setAttribute('aria-pressed',String(theme==='dark'));
  try{localStorage.setItem('tizhuang:studio-theme',theme);}catch{}
}
let initialTheme='light';try{initialTheme=localStorage.getItem('tizhuang:studio-theme')==='dark'?'dark':'light';}catch{}
setTheme(initialTheme);
$('#theme-toggle').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
$('#skill-update').onclick=()=>{
  showDialog('更新题库工作台',`<p>当前版本：<strong>1.0.1</strong></p><p>更新时仅替换工作台程序，保留整个题库目录、题目和组卷篮。</p><p>请让 Agent 按官方安装说明检查版本；同版跳过，旧版备份后更新。</p><button id="update-agent" class="primary">复制给 Agent 的更新指令</button><a href="https://github.com/weishao2/tizhuang-agent-skills" target="_blank" rel="noopener">查看题庄技能发布目录 ↗</a>`);
  $('#update-agent').onclick=()=>{$('#library-dialog').close();promptAgent('检查 tizhuang-studio 的官方版本与更新说明。请读取 https://tizhuang.qcscience.cc/studio/INSTALL.md；当前为 1.0.1，如有新版本，仅更新这个工作台的程序文件，保留本工作区的全部题目、组卷篮、目录和配置，不修改 question-bank 与 tizhuang-local-bank。没有可验证的新版本时说明情况，不安装其他技能替代。');};
};
// The first state request can finish before this final deferred script loads.
if(state)render();
