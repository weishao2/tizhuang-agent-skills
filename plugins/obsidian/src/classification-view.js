import {Modal,Notice} from 'obsidian';
export class AutoClassifyModal extends Modal{
 constructor(view,batch){super(view.app);this.view=view;this.batch=batch;}
 onOpen(){
  const root=this.contentEl;root.classList.add('tz-classify');const heading=document.createElement('h2');heading.textContent='自动分类';root.append(heading);
  const copy=document.createElement('p');copy.textContent='为未关联知识点的题目补齐分类。先按已有考点标签匹配本地知识树，无法确定的题交给 Agent 判断。教材章节保持原样。';root.append(copy);
  const status=document.createElement('p');status.className='tz-status';root.append(status);
  const start=document.createElement('button');start.textContent=this.batch?'分类本次导入':'分类所有未关联题目';start.className='mod-cta';root.append(start);
  start.onclick=async()=>{start.disabled=true;status.textContent='正在检查本地题目与知识树……';try{const result=await this.view.plugin.runLocal('auto-classify',this.batch?['--batch',this.batch]:[]);status.textContent=result.considered?`已关联 ${result.classified} 题，${result.pending} 题待 Agent 判断。`:'全部题目都已关联知识点。';start.remove();if(result.report){const report=document.createElement('button');report.textContent='查看分类报告';report.onclick=()=>this.view.openFile(result.report.replace(this.app.vault.adapter.getBasePath(),'').replace(/^[\\/]/,'').replace(/\\/g,'/'));root.append(report);}if(result.pending){const prompt=`使用 tizhuang-local-bank，继续题库“${this.app.vault.adapter.getBasePath()}”的知识点分类任务。读取报告“${result.report}”及对应 result.json，只处理其中待判断的题目。阅读原文与配图，匹配本地标准知识树的真实节点；综合题可关联多个。生成并验证 classify 清单后应用，保留正文、分值、审核状态，暂不分教材章节。`;const area=document.createElement('textarea');area.readOnly=true;area.value=prompt;area.rows=4;root.append(area);const agent=document.createElement('button');agent.textContent='复制 Agent 分类指令';agent.onclick=async()=>{try{await window.navigator.clipboard.writeText(prompt);new Notice('已复制，请交给你使用的 Agent。');}catch{area.focus();area.select();}};root.append(agent);}await this.view.refresh();}catch(error){status.textContent=error.message;start.disabled=false;}};
 }
 onClose(){this.contentEl.replaceChildren();}
}
