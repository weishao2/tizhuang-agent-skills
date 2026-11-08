 'use strict';
function paperScopeLabels(paper){
  const lists=localScopeLists();
  return (paper.scopes||[]).map(s=>`${lists.phases.find(p=>String(p.id)===String(s.phase_id))?.name||''}${lists.subjects.find(p=>String(p.id)===String(s.subject_id))?.name||''}`).filter(Boolean);
}
function paperTopics(paper,catalogs){
  const topics=[];
  for(const q of paper.classifications||[]){
    let mapped=false;
    for(const c of catalogs){
      if(String(c.phase_id)!==String(q.phase_id)||String(c.subject_id)!==String(q.subject_id))continue;
      if(c.kind==='chapter'&&String(c.edition_id)!==String(q.edition_id))continue;
      const ids=(q[c.kind==='chapter'?'chapter_ids':'knowledge_tree_ids']||[]).map(String);
      for(const n of c.nodes||[])if(ids.includes(String(n.id))){topics.push({name:n.name,kind:c.kind==='chapter'?'章节':'知识点'});if(c.kind==='knowledge')mapped=true;}
    }
    if(!mapped&&typeof q.knowledge==='string')for(const name of q.knowledge.split(/[、,，;；]/).map(s=>s.trim()).filter(Boolean))topics.push({name,kind:'知识点'});
  }
  return topics.filter((t,i)=>topics.findIndex(x=>x.name===t.name&&x.kind===t.kind)===i);
}
function filterPapers(rows,filters,catalogs,scopeLabel=paperScopeLabels){
  const term=(filters.query||'').trim().toLocaleLowerCase();
  return rows.filter(p=>{
    const scopes=(p.scopes||[]).map(s=>`${s.phase_id}:${s.subject_id}`);
    if(filters.scope&&!scopes.includes(filters.scope))return false;
    if(filters.tag&&!(p.tags||[]).includes(filters.tag))return false;
    const text=[p.display_title||p.title,p.id,...scopeLabel(p),...paperTopics(p,catalogs).map(t=>t.name),...(p.tags||[])].join(' ').toLocaleLowerCase();
    return !term||text.includes(term);
  }).sort((a,b)=>{const comparison=String(a.created_at||a.id).localeCompare(String(b.created_at||b.id));return filters.order==='oldest'?comparison:-comparison;});
}
let paperFilters={query:'',scope:'',tag:'',order:'newest'};
const paperIcons={
  print:'<path d="M6 9V3h12v6M6 17H4V9h16v8h-2M6 14h12v7H6z"/><path d="M17 12h.01"/>',
  eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  edit:'<path d="m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15z"/>'
};
function paperIcon(name){return `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paperIcons[name]}</svg>`;}
function paperMenu(label,icon,body){return `<details class="paper-menu"><summary title="${label}" aria-label="${label}">${paperIcon(icon)}<span class="menu-triangle" aria-hidden="true">▾</span></summary><div class="paper-menu-pop">${body}</div></details>`;}
function paperBadgeRow(paper){
  const topics=paperTopics(paper,state.catalogs),tags=paper.tags||[];
  const badges=[...paperScopeLabels(paper).map(name=>({name,kind:'学科学段'})),...topics,...tags.map(name=>({name,kind:'标签'}))];
  const shown=badges.slice(0,4),rest=badges.slice(4);
  const badge=t=>`<span class="paper-tag ${t.kind==='学科学段'?'paper-scope':''}" title="${esc(t.kind+'：'+t.name)}">${esc(t.name)}</span>`;
  return shown.map(badge).join('')+(rest.length?`<details class="paper-menu paper-more"><summary aria-label="查看其余 ${rest.length} 个分类标签">+${rest.length} <span class="menu-triangle" aria-hidden="true">▾</span></summary><div class="paper-menu-pop paper-all-tags">${rest.map(badge).join('')}</div></details>`:'')+`<button class="paper-tag-add" data-paper-tags="${esc(paper.id)}" title="编辑标签" aria-label="编辑标签">＋</button>`;
}
renderExports=function(){
  const rows=filterPapers(state.exports,paperFilters,state.catalogs);
  const active=paperFilters.query;
  const toolbar=`<div class="paper-filters" role="search" aria-label="搜索试卷"><input id="paper-search" class="search" aria-label="搜索试卷" placeholder="搜索名称、知识点、章节或标签…" value="${esc(paperFilters.query)}">${active?'<button id="paper-filter-reset" class="quiet">清除搜索</button>':''}</div>`;
  main.innerHTML=`<div class="section-title"><div><h1>我的试卷 <small class="paper-count">${active?rows.length+'/':''}${state.exports.length} 份</small></h1></div><button class="secondary" data-go="basket">去组卷 →</button></div>${state.exports.length?toolbar:''}<div class="papers-list">${rows.map(e=>`<article class="export-row paper-card compact-paper" data-paper-id="${esc(e.id)}"><div class="paper-heading"><h3><button class="paper-title-button" data-paper-rename="${esc(e.id)}" title="点击修改名称">${esc(e.display_title||e.title)}</button></h3><div class="paper-icon-actions">${paperMenu('打印与下载','print',`${e.student_html?`<button data-paper-print="${esc(e.student_html)}">打印无答案版</button><button data-paper-print="${esc(e.teacher_html)}">打印教师答案版</button>`:''}<div class="paper-menu-divider"></div><a href="${esc(e.student)}">下载无答案 Word</a><a href="${esc(e.teacher)}">下载教师答案 Word</a>`)}${e.student_html?paperMenu('预览','eye',`<a href="${esc(e.student_html)}" target="_blank" rel="noopener">预览无答案版 ↗</a><a href="${esc(e.teacher_html)}" target="_blank" rel="noopener">预览教师答案版 ↗</a>`):''}<button class="paper-icon" data-paper-open="${esc(e.id)}" aria-label="继续编辑" title="继续编辑" ${e.snapshot_available===false?'disabled data-disabled="true"':''}>${paperIcon('edit')}</button></div></div><div class="paper-meta-line"><span class="paper-facts" title="试卷编号 ${esc(e.id)}">${esc(e.created_at)}<span>·</span>${e.count} 题${e.total_score==null?'':`<span>·</span>${e.total_score} 分`}${e.duration_minutes==null?'':`<span>·</span>${e.duration_minutes} 分钟`}</span><span class="paper-meta-divider" aria-hidden="true"></span><div class="paper-badges">${paperBadgeRow(e)}</div></div><div class="print-links" hidden></div></article>`).join('')||(state.exports.length?'<div class="empty"><h3>没有匹配的试卷</h3><button class="secondary" id="paper-empty-reset">清除搜索</button></div>':'<div class="empty"><h3>还没有生成试卷</h3><button class="primary" data-go="basket">去组卷 →</button></div>')}</div>`;
  const search=$('#paper-search');
  if(search)search.oninput=()=>{paperFilters.query=search.value;const start=search.selectionStart,end=search.selectionEnd;renderExports();const next=$('#paper-search');next.focus();next.setSelectionRange(start,end);};
  for(const id of ['paper-filter-reset','paper-empty-reset']){const b=$('#'+id);if(b)b.onclick=()=>{paperFilters={query:'',scope:'',tag:'',order:'newest'};renderExports();$('#paper-search')?.focus();};}
  main.querySelectorAll('[data-paper-rename]').forEach(b=>b.onclick=()=>renamePaper(b,state.exports.find(e=>e.id===b.dataset.paperRename)));
  main.querySelectorAll('[data-paper-tags]').forEach(b=>b.onclick=()=>editPaperTags(state.exports.find(e=>e.id===b.dataset.paperTags)));
  main.querySelectorAll('[data-paper-open]').forEach(b=>b.onclick=()=>reopenPaper(state.exports.find(e=>e.id===b.dataset.paperOpen)));
  main.querySelectorAll('[data-paper-print]').forEach(b=>b.onclick=()=>printSavedPaper(b.dataset.paperPrint));
  main.querySelectorAll('.paper-menu').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)main.querySelectorAll('.paper-menu').forEach(other=>{if(other!==d)other.open=false;});}));
  bindNav();
};
function renamePaper(button,paper){
  const form=document.createElement('form');form.className='paper-rename-form';
  form.innerHTML=`<input aria-label="试卷名称" maxlength="120" required value="${esc(paper.display_title||paper.title)}" title="回车保存，Esc 取消"><small>回车保存 · Esc 取消</small>`;
  button.replaceWith(form);const input=form.querySelector('input');let saving=false,cancelled=false;
  const save=async()=>{if(saving||cancelled)return;const title=input.value.trim();if(!title){input.value=paper.display_title||paper.title;return;}if(title===(paper.display_title||paper.title)){form.replaceWith(button);return;}saving=true;input.disabled=true;const ok=await command('paper-update',{id:paper.id,title,tags:paper.tags||[]});if(ok)say('名称已保存；已有 Word 卷头保持原样，重新生成后使用新名称。');};
  form.onsubmit=e=>{e.preventDefault();save();};input.onblur=()=>save();input.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();cancelled=true;form.replaceWith(button);button.focus();}};input.focus();input.select();
}
function editPaperTags(paper){
  showDialog('编辑标签',`<form id="paper-tags-form"><label class="field">标签<input id="paper-tags" maxlength="260" placeholder="例如：期中复习、八年级、A 卷" value="${esc((paper.tags||[]).join('、'))}"></label><p class="tiny">逗号或顿号分隔，最多 10 个。学科学段、知识点与章节根据本卷题目显示。</p><div class="dialog-actions"><button type="button" class="quiet" id="paper-cancel">取消</button><button class="primary" type="submit">保存</button></div></form>`);
  $('#paper-cancel').onclick=()=>$('#library-dialog').close();
  $('#paper-tags-form').onsubmit=async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;try{const ok=await command('paper-update',{id:paper.id,title:paper.display_title||paper.title,tags:$('#paper-tags').value.split(/[,，、\n]/).map(t=>t.trim()).filter(Boolean)});if(ok){$('#library-dialog').close();say('标签已保存。');}else $('#library-dialog-message').textContent=$('#notice').textContent;}finally{button.disabled=false;}};
}
function printSavedPaper(url){
  main.querySelectorAll('.paper-menu').forEach(d=>d.open=false);
  // Export pages disallow framing. Open a normal local preview, then print it.
  const preview=window.open(url,'_blank');
  if(!preview)return say('浏览器阻止了打印窗口，请允许弹出窗口，或通过预览打开后打印。',true);
  let attempts=0;
  const timer=setInterval(async()=>{try{
    if(preview.closed){clearInterval(timer);return;}
    if(preview.location.pathname===url&&preview.document.readyState==='complete'){
      clearInterval(timer);
      if(!preview.document.querySelector('h1'))return say('试卷未加载成功，请刷新后重试。',true);
      await preview.document.fonts.ready;preview.focus();preview.print();
    }else if(++attempts>100){clearInterval(timer);say('打印稿加载较慢，可在预览窗口中使用浏览器打印。');}
  }catch{clearInterval(timer);say('请在已打开的预览窗口中使用浏览器打印。');}},150);
}
// Dismiss icon menus with Escape or by clicking outside.
document.addEventListener('click',e=>{if(!e.target.closest('.paper-menu'))document.querySelectorAll('.paper-menu[open]').forEach(d=>d.open=false);});
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.paper-menu[open]').forEach(d=>d.open=false);});
function reopenPaper(paper){
  showDialog('继续编辑这份试卷',`<p>恢复「${esc(paper.display_title||paper.title)}」的题序、分值和考试设置。</p><p>当前组卷篮中的 <strong>${state.items.length} 道题</strong>将被替换。题目使用本地题库当前内容，核对状态保持不变。原来的 Word 和打印稿保留，再次生成会新增一份试卷。</p><div class="dialog-actions"><button class="quiet" id="paper-open-cancel">取消</button><button class="primary" id="paper-open-confirm">替换组卷篮并继续编辑</button></div>`);
  $('#paper-open-cancel').onclick=()=>$('#library-dialog').close();
  $('#paper-open-confirm').onclick=async event=>{event.target.disabled=true;const ok=await command('paper-open',{id:paper.id,confirm:true});if(ok){$('#library-dialog').close();setTab('basket');say('已恢复本卷的题序与分值。修改后生成新稿，原稿保留。');}else{$('#library-dialog-message').textContent=$('#notice').textContent;event.target.disabled=false;}};
}
