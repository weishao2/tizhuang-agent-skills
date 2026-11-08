'use strict';
// Daily workflow extensions. Questions and cursors stay in the shared service;
// browser preferences are namespaced by the selected workspace.
function tagMatches(tags,tag){return !tag||tags.some(t=>t===tag||t.startsWith(tag+'/'));}
function tagHierarchy(questions){
  const map=new Map();
  for(const q of questions.filter(q=>!q.archived))for(const tag of q.tags){
    const parts=tag.split('/').filter(Boolean);
    for(let i=1;i<=parts.length;i++){
      const id=parts.slice(0,i).join('/');
      if(!map.has(id))map.set(id,{id,name:parts[i-1],parent_id:parts.slice(0,i-1).join('/'),ids:new Set()});
      map.get(id).ids.add(q.id);
    }
  }
  return [...map.values()].sort((a,b)=>a.id.localeCompare(b.id,'zh-CN'));
}
function startSteps(s){
  const rows=s.questions.filter(q=>!q.archived);
  return [
    {title:'下载知识树',done:s.catalogs.some(c=>c.kind==='knowledge'),action:'catalog',cta:'下载目录',hint:'选好学段和学科，把知识树保存在本机。'},
    {title:'放入第一批题',done:rows.length>0,action:'find',cta:'网站取题',hint:'从网站取题，也可以导入自己的 PDF。'},
    {title:'核对题目',done:rows.some(q=>q.status==='reviewed'),action:'review',cta:'去核对',hint:'查看题干、答案和配图，再由你确认已核对。'},
    {title:'组出第一张试卷',done:s.exports.length>0,action:'basket',cta:'去组卷',hint:'将已核对题目加入组卷篮，调整后导出 Word 双版。'}
  ];
}
function cleanPreferences(raw){
  const v=raw&&typeof raw==='object'?raw:{}, f=v.library&&typeof v.library==='object'?v.library:{};
  const library={};
  for(const k of ['catalog','node','tag','type','query','subject'])library[k]=typeof f[k]==='string'?f[k].slice(0,300):'';
  library.status=['draft','reviewed','unclassified'].includes(f.status)?f.status:'';
  library.unused=f.unused===true;library.archived=f.archived===true;library.page=0;
  return {library,count:Number.isInteger(v.count)&&v.count>=1&&v.count<=20?v.count:5};
}
function scopeCursorKey(s){return JSON.stringify(['subject_id','phase_id','edition_id','grade_id','chapter_id','knowledge_tree_id','keyword'].map(k=>String(s[k]||'')));}
function selectionVisible(c,edition){return c.kind==='knowledge'||String(c.edition_id)===String(edition);}

let preferencesWorkspace='';
function restorePreferences(){
  if(!state||preferencesWorkspace===state.workspace)return;
  preferencesWorkspace=state.workspace;let raw={};
  try{raw=JSON.parse(localStorage.getItem('tizhuang:workflow:'+state.workspace)||'{}');}catch{}
  const pref=cleanPreferences(raw);lf=pref.library;fetchCount=pref.count;
  const c=state.catalogs.find(c=>c.id===lf.catalog);
  if(!c){lf.catalog='';lf.node='';}else if(!c.nodes.some(n=>String(n.id)===lf.node))lf.node='';
}
function rememberWorkflow(){if(state)try{localStorage.setItem('tizhuang:workflow:'+state.workspace,JSON.stringify({library:lf,count:fetchCount}));}catch{}}
const workflowRender=render;
render=function(){restorePreferences();workflowRender();rememberWorkflow();};
main.addEventListener('change',rememberWorkflow);
main.addEventListener('input',rememberWorkflow);

const workflowHome=renderHome;
renderHome=function(){
  workflowHome();const steps=startSteps(state),current=steps.findIndex(x=>!x.done);
  const box=document.createElement('section');box.className='lib-panel start-guide';
  box.innerHTML=`<h3>四步用起来${current<0?' · 已完成':''}</h3><div class="start-guide-steps">${steps.map((x,i)=>`<div class="start-step ${x.done?'done':i===current?'current':''}"><span class="step-number">${x.done?'✓':i+1}</span><div><strong>${x.title}</strong>${i===current?`<p>${x.hint}</p><button class="secondary" data-start="${x.action}">${x.cta}</button>${i===1?' <button class="quiet" data-start="pdf">导入 PDF</button>':''}`:''}</div></div>`).join('')}</div>`;
  main.querySelector('.home-actions').after(box);
  box.querySelectorAll('[data-start]').forEach(b=>b.onclick=()=>{
    const go=b.dataset.start;
    if(go==='catalog')return openCatalog();
    if(go==='review'){lf={...cleanPreferences({}).library,status:'draft'};setTab('library');}
    else {if(go==='find')source='online';setTab(go);}
  });
};

const workflowFind=renderFind;
renderFind=function(){
  workflowFind();if(source!=='online')return;
  $('#fetch-count').oninput=e=>{const n=Number(e.target.value);if(Number.isInteger(n)&&n>=1&&n<=20){fetchCount=n;rememberWorkflow();}};
  const offset=state.fetch_cursors?.[scopeCursorKey(scope)]||0;
  const info=document.createElement('p');info.className='tiny';info.id='fetch-progress';
  info.textContent=offset?`当前范围已取 ${offset} 题，下次从第 ${offset+1} 题继续。`:'取题进度按范围保存在本机，刷新后可继续。';
  $('#fetch').after(info);
  $('#fetch').onclick=async()=>{
    if(!state.connected)return openConnection();
    const count=Number($('#fetch-count').value);fetchCount=count;rememberWorkflow();
    say('正在获取题目与配图，请稍候…');
    if(await command('fetch',{...scope,count})){
      keyword='';localType='';say('取题结果与进度已保存到工作台，可继续勾选组卷。');render();
    }
    try{quota=await api('quota');head();if($('#quota-note'))$('#quota-note').textContent=`当前可用 ${Math.min(quota.remaining,quota.member_remaining??quota.remaining)} 题`;}catch{}
  };
};

const workflowFilter=filteredQuestions;
filteredQuestions=function(){const tag=lf.tag;try{lf.tag='';return workflowFilter().filter(q=>tagMatches(q.tags,tag));}finally{lf.tag=tag;}};
const workflowLibrary=renderLibrary;
renderLibrary=function(){
  workflowLibrary();rememberWorkflow();
  const area=main.querySelector('.tree-panel .chip-list'),model=directoryPickerModel(tagHierarchy(state.questions));
  const counts=new Map(tagHierarchy(state.questions).map(n=>[n.id,n.ids.size]));
  function branch(parent,depth=0){if(depth>60)return '';return (model.children.get(parent)||[]).map(n=>{
    const button=`<button class="tree-node ${lf.tag===n.id?'chosen':''}" data-tag="${esc(n.id)}"><span>${esc(n.name)}</span><small>${counts.get(n.id)}</small></button>`;
    return model.children.has(n.id)?`<details ${lf.tag===n.id||lf.tag.startsWith(n.id+'/')?'open':''}><summary>${button}</summary><div class="tree-children">${branch(n.id,depth+1)}</div></details>`:button;
  }).join('');}
  area.className='tag-tree';area.innerHTML=`<button class="tree-node ${!lf.tag?'chosen':''}" data-tag="">全部标签</button>${branch('')||'<p class="tiny">可添加“期中/易错题”这样的分层标签。</p>'}`;
  area.querySelectorAll('[data-tag]').forEach(b=>b.onclick=e=>{e.preventDefault();lf.tag=b.dataset.tag;lf.page=0;render();});
};

classifyQuestions=function(ids){
  if(!ids.length)return say('请先勾选本页题目。');
  const qs=state.questions.filter(q=>ids.includes(q.id));
  if(new Set(qs.map(q=>q.subject_id+'-'+q.phase_id)).size>1)return say('请按同一学科学段分批分类。',true);
  const q=qs[0],cats=state.catalogs.filter(c=>c.subject_id===q.subject_id&&c.phase_id===q.phase_id),expected=hashes(ids);
  const common=field=>qs.reduce((all,x)=>all.filter(v=>x[field].includes(v)),q[field]);
  const selections=new Map(cats.map(c=>[c.id,new Set(common(c.kind==='knowledge'?'knowledge_tree_ids':'chapter_ids').filter(id=>c.nodes.some(n=>String(n.id)===String(id))).map(String))]));
  const models=new Map(cats.map(c=>[c.id,directoryPickerModel(c.nodes)]));
  showDialog(`分类与标签 · ${ids.length} 题`,`<p>保存后将用本次勾选替换所选题目的分类和标签，题干与答案不变。</p><label class="field">教材目录<select id="class-edition">${option(cats.filter(c=>c.kind==='chapter').map(c=>({id:c.edition_id,name:c.label})),q.edition_id,'不设置教材')}</select></label><label class="field">搜索知识点或章节<input id="class-search" placeholder="输入名称或完整路径关键词"></label><p id="class-selected" class="tiny" aria-live="polite"></p><div class="classification-options" id="class-trees"></div><label class="field">标签（逗号分隔，斜杠表示层级）<input id="class-tags" value="${esc(common('tags').join('，'))}" placeholder="例如：期中/易错题，基础练习"></label><div class="lib-actions"><button class="primary" id="save-classification">保存分类</button><button class="secondary" id="agent-classification">让 Agent 读题分类</button></div>`);
  const openNodes=new Set();
  for(const c of cats)for(const id of selections.get(c.id)){
    let n=models.get(c.id).byId.get(id);while(n){openNodes.add(c.id+':'+n.id);n=models.get(c.id).byId.get(n.parent_id);}
  }
  const visibleCats=()=>cats.filter(c=>selectionVisible(c,$('#class-edition').value));
  const updateCount=()=>{$('#class-selected').textContent=`已选 ${visibleCats().reduce((n,c)=>n+selections.get(c.id).size,0)} 个节点（搜索只筛选显示，不会取消勾选）`;};
  function paint(){
    const term=$('#class-search').value.trim();
    $('#class-trees').innerHTML=visibleCats().map(c=>{
      const model=models.get(c.id),selected=selections.get(c.id);
      const row=(n,search=false)=>`<label class="class-node"><input type="checkbox" data-class-catalog="${esc(c.id)}" value="${esc(n.id)}" ${selected.has(n.id)?'checked':''}><span>${esc(n.name)}${search?`<small>${esc(model.path(n.id))}</small>`:''}</span></label>`;
      function branch(parent,depth=0){if(depth>60)return '';return (model.children.get(parent)||[]).map(n=>model.children.has(n.id)?`<details data-class-expand="${esc(c.id+':'+n.id)}" ${openNodes.has(c.id+':'+n.id)?'open':''}><summary>${esc(n.name)}</summary><div class="tree-children">${row(n)}${branch(n.id,depth+1)}</div></details>`:row(n)).join('');}
      const hits=term?model.search(term):[];
      return `<fieldset><legend>${esc(c.label)}</legend>${term?(hits.slice(0,100).map(n=>row(n,true)).join('')||'<p class="tiny">没有匹配的节点</p>')+(hits.length>100?'<p class="tiny">只显示前 100 项，请补充关键词。</p>':''):branch('')}</fieldset>`;
    }).join('')||'<p>还没有对应目录，请先下载知识树或教材目录。</p>';
    $('#class-trees').querySelectorAll('[data-class-expand]').forEach(d=>d.ontoggle=()=>{d.open?openNodes.add(d.dataset.classExpand):openNodes.delete(d.dataset.classExpand);});
    $('#class-trees').querySelectorAll('input[type=checkbox]').forEach(el=>el.onchange=()=>{const selected=selections.get(el.dataset.classCatalog);el.checked?selected.add(el.value):selected.delete(el.value);updateCount();});
    updateCount();
  }
  $('#class-search').oninput=paint;$('#class-edition').onchange=paint;paint();
  $('#agent-classification').onclick=()=>{$('#library-dialog').close();classificationPrompt(ids);};
  $('#save-classification').onclick=async()=>{
    const checked=kind=>visibleCats().filter(c=>c.kind===kind).flatMap(c=>[...selections.get(c.id)]);
    try{await lib('classify',{ids,hashes:expected,knowledge_tree_ids:checked('knowledge'),chapter_ids:checked('chapter'),edition_id:$('#class-edition').value?Number($('#class-edition').value):null,tags:$('#class-tags').value.split(/[,，]/).map(t=>t.trim()).filter(Boolean)});$('#library-dialog').close();say('分类已保存。');}catch(e){dialogError(e);}
  };
};
