import {MarkdownRenderer,Notice,Modal} from 'obsidian';
import {cleanTitle,hasImage} from './presentation.js';
const E=(p,t,text,cls)=>{const e=document.createElement(t);if(text!=null)e.textContent=text;if(cls)e.className=cls;p.append(e);return e;};
const B=(p,text,fn,cls='tz-quiet')=>{const b=E(p,'button',text,cls);b.type='button';b.onclick=fn;return b;};
class ClearBasketModal extends Modal{
 constructor(app,done){super(app);this.done=done;}
 onOpen(){E(this.contentEl,'h2','清空组卷篮？');E(this.contentEl,'p','题库原题和已生成试卷会保留。');B(this.contentEl,'保留',()=>this.close());B(this.contentEl,'清空组卷篮',async()=>{await this.done();this.close();},'tz-primary');}
 onClose(){this.contentEl.replaceChildren();}
}
export function basketBar(view,parent){
 const bar=E(parent,'div',null,'tz-basket-bar');view.basketBarEl=bar;updateBasketBar(view);return bar;
}
export function updateBasketBar(view){
 const b=view.plugin.basket;if(!view.basketBarEl)return;view.basketBarEl.replaceChildren();E(view.basketBarEl,'span',`已选 ${b.data.items.length} 题 · ${b.total()} 分`);B(view.basketBarEl,'查看组卷篮',()=>view.show('basket'),'tz-primary');
 const tab=view.contentEl.querySelector('[data-tab="basket"]');if(tab)tab.textContent=`组卷篮${b.data.items.length?'（'+b.data.items.length+'）':''}`;
}
export function drawBasket(view){
 const basket=view.plugin.basket,root=view.body;root.replaceChildren();const heading=E(root,'div',null,'tz-paper-heading');const title=E(heading,'div');E(title,'h2','把好题，排成一张卷。');E(title,'p','拖动排题序，单独设分值；生成时保留原题、公式和配图。','tz-muted');B(heading,'继续选题',()=>view.show('questions'));
 if(!basket.data.items.length){const empty=E(root,'div',null,'tz-basket-empty');E(empty,'h3','组卷篮还是空的');E(empty,'p','在“我的题目”中勾选，跨章节选题也会保留。','tz-muted');B(empty,'去本地题库选题',()=>view.show('questions'),'tz-primary');return;}
 const missing=basket.data.items.filter(i=>!view.catalog.rows.some(r=>r.q.id===i.question_id));const drafts=basket.data.items.filter(i=>view.catalog.rows.find(r=>r.q.id===i.question_id)?.q.status!=='reviewed');
 const workspace=E(root,'fieldset',null,'tz-paper-workspace'),list=E(workspace,'section',null,'tz-paper-basket-list'),aside=E(workspace,'aside',null,'tz-paper-settings');
 let status,generate,confirmed;const fail=error=>{status.textContent=error.message;status.classList.add('tz-error');};const mutate=async(fn,redraw=true)=>{try{await fn();if(redraw)drawBasket(view);else{status.textContent='已保存';root.querySelector('.tz-paper-total strong').textContent=String(basket.total());root.querySelector('.tz-paper-success')?.remove();}updateBasketBar(view);}catch(error){fail(error);}};
 const top=E(list,'div',null,'tz-local-summary');E(top,'strong',`${basket.data.items.length} 道题，按当前顺序生成`);B(top,'清空',()=>new ClearBasketModal(view.app,()=>mutate(()=>basket.clear())).open());
 for(const [index,item]of basket.data.items.entries()){
  const row=view.catalog.rows.find(r=>r.q.id===item.question_id),q=row?.q;const card=E(list,'article',null,'tz-question tz-basket-card');card.dataset.questionId=item.question_id;
  card.ondragover=event=>event.preventDefault();card.ondrop=event=>{event.preventDefault();const id=event.dataTransfer.getData('text/tizhuang-question');if(basket.has(id))mutate(()=>basket.move(id,index));};
  const head=E(card,'div',null,'tz-question-head'),handle=E(head,'span','⠿','tz-drag-handle');handle.draggable=true;handle.title='拖动调整题序';handle.ondragstart=event=>{event.dataTransfer.setData('text/tizhuang-question',item.question_id);event.dataTransfer.effectAllowed='move';};E(head,'strong',String(index+1),'tz-order');E(head,'span',q?.type||'题目缺失','tz-type');E(head,'span',q?.status==='reviewed'?'已核对':'待核对','tz-local-status');
  const body=E(card,'div',null,'tz-local-title');if(q&&hasImage(q))E(body,'span','[图]','tz-image-label');E(body,'span',q?cleanTitle(q.title,q.type):'这道题已被移走或删除，请从组卷篮移除后再生成。');
  const tools=E(card,'div',null,'tz-basket-item-tools');const scoreLabel=E(tools,'label','本题 '),score=E(scoreLabel,'input');score.type='number';score.value=item.score;score.min='0';score.max='1000';score.step='0.01';score.required=true;score.setAttribute('aria-label',`第 ${index+1} 题分值`);E(scoreLabel,'span',' 分');score.onchange=()=>mutate(()=>basket.score(item.question_id,score.value),false);
  const up=B(tools,'上移',()=>mutate(()=>basket.move(item.question_id,index-1)));up.disabled=index===0;up.setAttribute('aria-label',`上移第 ${index+1} 题`);const down=B(tools,'下移',()=>mutate(()=>basket.move(item.question_id,index+1)));down.disabled=index===basket.data.items.length-1;down.setAttribute('aria-label',`下移第 ${index+1} 题`);B(tools,'移除',()=>mutate(()=>basket.remove(item.question_id)));
  if(q){const detail=E(card,'div',null,'tz-question-details');detail.hidden=true;let rendered=false;B(tools,'查看原题与答案',async event=>{detail.hidden=!detail.hidden;event.currentTarget.textContent=detail.hidden?'查看原题与答案':'收起';if(!rendered){try{for(const [key,name]of [['content','题目'],['answer','答案'],['analysis','解析']]){if(!q[key])continue;const section=E(detail,'section',null,'tz-detail-section');E(section,'h4',name);const content=E(section,'div',null,'tz-preview');const text=q[key].replace(/Assets\/([a-f0-9]+\.[a-z0-9]+)/g,(_,f)=>{const path=view.plugin.store.assetDir+'/'+f,target=view.app.vault.getAbstractFileByPath(path);return target?view.app.vault.getResourcePath(target):path;});await MarkdownRenderer.render(view.app,text,content,row.path,view);}rendered=true;}catch(error){fail(error);}}});}
 }
 E(aside,'h3','试卷设置');const nameLabel=E(aside,'label','试卷标题','tz-label'),name=E(nameLabel,'input');name.value=basket.data.title;name.maxLength=120;name.required=true;name.setAttribute('aria-label','试卷标题');name.onchange=()=>mutate(()=>basket.settings({title:name.value}),false);
 const field=(label,key,min,max,unit)=>{const l=E(aside,'label',label,'tz-label'),line=E(l,'div',null,'tz-paper-number'),input=E(line,'input');input.type='number';input.min=min;input.max=max;input.step='1';input.required=true;input.value=basket.data[key];input.setAttribute('aria-label',label);E(line,'span',unit);input.onchange=()=>mutate(()=>basket.settings({[key]:input.value===''?NaN:Number(input.value),...(key==='duration_minutes'?{duration_custom:true}:{})}),false);};
 field('考试时长','duration_minutes',1,600,'分钟');field('每题作答留白','answer_space_mm',0,100,'毫米');const total=E(aside,'div',null,'tz-paper-total');E(total,'span','试卷总分');E(total,'strong',String(basket.total()));E(total,'small',`${basket.data.items.length} 题`);
 E(aside,'p','时长按学科学段建议，可自由调整；分值只用于本卷。','tz-muted');
 if(missing.length)E(aside,'p',`${missing.length} 道题已不存在，请先移除。`,'tz-error');
 if(drafts.length&&!missing.length){const label=E(aside,'label',null,'tz-review-check');confirmed=E(label,'input');confirmed.type='checkbox';confirmed.setAttribute('aria-label','已逐题核对待核对题');E(label,'span',`我已逐题核对这 ${drafts.length} 道待核对题的题干、答案和图片。`);confirmed.onchange=()=>generate.disabled=!confirmed.checked;}
 status=E(aside,'p',null,'tz-status');generate=B(aside,'生成试卷与教师答案',async()=>{for(const input of workspace.querySelectorAll('input'))if(!input.reportValidity())return;workspace.disabled=true;status.textContent='正在整理题序、分值和本地图片……';try{await basket.generate(view.plugin,!!confirmed?.checked);await view.catalog.load();await view.catalog.writeHome();drawBasket(view);}catch(error){fail(error);workspace.disabled=false;generate.textContent='重试生成';}},'tz-primary tz-paper-generate');generate.disabled=!!missing.length||!!drafts.length;
 E(aside,'p','本地生成 Word 双版，可继续编辑；另附打印稿，可存为 PDF。','tz-muted');
 if(basket.data.last_result){const result=basket.data.last_result,box=E(aside,'div',null,'tz-paper-success');E(box,'strong','两份试卷已保存');if(result.student_docx&&result.teacher_docx){B(box,'编辑无答案 Word',()=>view.plugin.openLocalOutput(result.student_docx),'tz-primary');B(box,'编辑教师答案 Word',()=>view.plugin.openLocalOutput(result.teacher_docx));}else{E(box,'p','这份旧卷仅有打印稿，生成新一版即可同时获得 Word。','tz-muted');}B(box,'打开无答案试卷',()=>view.plugin.openLocalOutput(result.student));B(box,'打开教师答案版',()=>view.plugin.openLocalOutput(result.teacher));B(box,'开始新一版',async()=>{await basket.save();await view.catalog.load();drawBasket(view);});B(box,'查看试卷记录',()=>view.openFile(result.note.replace(/\\/g,'/').slice(view.app.vault.adapter.getBasePath().replace(/\\/g,'/').length+1)));}
}
