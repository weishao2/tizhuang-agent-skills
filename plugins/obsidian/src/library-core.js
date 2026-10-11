import YAML from 'yaml';
import {readNote} from './core.js';
import {nativeTags,cleanTitle,hasImage,groupFolder} from './presentation.js';
export class LocalCatalog{
 constructor(store){this.store=store;this.rows=[];this.errors=[];this.trees=[];this.names={};}
 async load(){
  await this.store.init();this.rows=[];this.errors=[];this.trees=[];
  for(const path of await this.store.files('题目库')){try{const q=readNote(await this.store.io.read(path));if(q.schema!=='tizhuang.question/v1'||!q.id)throw Error('不是有效题目');this.rows.push({path,q});}catch(e){this.errors.push({path,message:e.message});}}
  this.names=await this.store.json('.bank/catalog/names.json',{subjects:{},phases:{},editions:{}});
  for(const [folder,kind]of [['.bank/taxonomy','knowledge'],['.bank/textbooks','chapter']])for(const path of await this.store.files(folder,'.json')){try{const data=await this.store.json(path);if(!Array.isArray(data.nodes))continue;const scope=[data.subject_id,data.phase_id,...(kind==='chapter'?[data.edition_id]:[])].join('-');this.trees.push({...data,kind,scope});}catch(e){this.errors.push({path,message:e.message});}}
  this.papers=(await this.store.files('试卷')).filter(p=>p.endsWith('/试卷.md'));
  this.paperTitles=new Map();for(const path of this.papers){const data=await this.store.json(path.replace(/试卷\.md$/,'manifest.json'));const text=await this.store.io.read(path);this.paperTitles.set(path,data.title||text.match(/^#\s+(.+)$/m)?.[1]||path.split('/').at(-2));}
  this.imports=[];for(const path of await this.store.files('.bank/imports','.json'))if(path.endsWith('/manifest.json')){try{this.imports.push(await this.store.json(path));}catch{this.errors.push({path,message:'导入记录无法读取'});}}
  const reports=await this.store.files('待整理');for(const batch of this.imports)batch.reportPath=reports.find(p=>p.endsWith(' · '+batch.id.slice(0,6)+'.md'));
  this.imports.sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));return this;
 }
 scopeTitle(tree){return [this.names.phases?.[tree.phase_id]||`学段${tree.phase_id}`,this.names.subjects?.[tree.subject_id]||`学科${tree.subject_id}`,tree.kind==='chapter'?(this.names.editions?.[tree.edition_id]||`教材${tree.edition_id}`):'知识点'].join(' · ');}
 treeMatch(q,tree){return String(q.subject_id)===String(tree.subject_id)&&String(q.phase_id)===String(tree.phase_id)&&(tree.kind!=='chapter'||String(q.edition_id)===String(tree.edition_id));}
 descendants(tree,id){const set=new Set([String(id)]);let more=true;while(more){more=false;for(const n of tree.nodes)if(set.has(String(n.parent_id))&&!set.has(String(n.id))){set.add(String(n.id));more=true;}}return set;}
 select(filter={}){
  const tree=this.trees.find(t=>t.scope===filter.scope&&t.kind===filter.kind);const ids=tree&&filter.node?this.descendants(tree,filter.node):null;
  return this.rows.filter(({q})=>{
   if(filter.status&&q.status!==filter.status)return false;
   if(filter.unclassified&&q.knowledge_tree_ids.length+q.chapter_ids.length)return false;
   if(filter.tag&&!q.tags.some(t=>t===filter.tag||t.startsWith(filter.tag+'/')))return false;
   if(filter.type&&q.type!==filter.type)return false;
   if(filter.kind==='knowledge'||filter.kind==='chapter'){if(!tree||!this.treeMatch(q,tree))return false;if(ids&&!q[filter.kind==='knowledge'?'knowledge_tree_ids':'chapter_ids'].some(id=>ids.has(String(id))))return false;}
   if(filter.query&&!`${q.title}\n${q.content}\n${q.search_text}\n${q.tags.join(' ')}`.toLocaleLowerCase().includes(filter.query.toLocaleLowerCase()))return false;
   return true;
  });
 }
 tagTree(){const map=new Map();for(const {q}of this.rows)for(const tag of q.tags){const parts=tag.split('/');for(let i=1;i<=parts.length;i++){const path=parts.slice(0,i).join('/');if(!map.has(path))map.set(path,{id:path,name:parts[i-1],parent_id:parts.slice(0,i-1).join('/'),ids:new Set()});map.get(path).ids.add(q.id);}}return [...map.values()].sort((a,b)=>a.id.localeCompare(b.id,'zh-CN'));}
 async classify(path,{tags,knowledge}){
  const original=await this.store.io.read(path),q=readNote(original);const tree=this.trees.find(t=>t.kind==='knowledge'&&this.treeMatch(q,t));knowledge=knowledge.map(String);
  if(knowledge.length&&(!tree||knowledge.some(id=>!tree.nodes.some(n=>String(n.id)===id))))throw Error('知识点不属于该题的学科学段。');
  const m=original.match(/^\uFEFF?---\r?\n([\s\S]*?)\r?\n---\r?\n/),meta=YAML.parse(m[1]);delete meta['标签'];delete meta.knowledge_tree_ids;meta.tags=nativeTags(tags);meta['知识节点编号']=knowledge;meta['精确知识编号']=(tree?.nodes||[]).filter(n=>knowledge.includes(String(n.id))&&n.knowledge_id!=null).map(n=>String(n.knowledge_id));
  let body=original.slice(m[0].length);const managed=/<!-- bank:knowledge:start -->[\s\S]*?<!-- bank:knowledge:end -->/g;
  if(body.includes('<!-- bank:knowledge:')){
   if((body.match(managed)||[]).length!==1)throw Error('知识关联区块标记不完整，请检查笔记。');
   const mapping=await this.store.json('.bank/ui-paths.json',{}),paths=mapping.knowledge?.[`${q.subject_id}-${q.phase_id}`]||{};
   const links=knowledge.map(id=>{const name=tree.nodes.find(n=>String(n.id)===id).name,p=paths[id];return '- '+(p?`[[${p.replace(/\.md$/,'')}|${name}]]`:name);}).join('\n');
   body=body.replace(managed,()=>knowledge.length?`<!-- bank:knowledge:start -->\n## 知识点分类\n\n${links}\n<!-- bank:knowledge:end -->`:'');
  }
  const backup='.bank/backups/'+q.id+'-'+crypto.randomUUID()+'.md';await this.store.mkdir('.bank/backups');await this.store.io.write(backup,original);
  if(await this.store.io.read(path)!==original)throw Error('题目刚被其他操作修改，请刷新后重试。');
  await this.store.io.write(path,'---\n'+YAML.stringify(meta,{version:'1.1'})+'---\n'+body);await this.load();return q.id;
 }
 async writeHome(){
  const reviewed=this.rows.filter(r=>r.q.status==='reviewed').length;let text=`# 题库首页\n\n共 **${this.rows.length}** 题 · 已核对 **${reviewed}** 题 · 待核对 **${this.rows.length-reviewed}** 题 · 试卷 **${this.papers.length}** 份\n\n\`\`\`tizhuang-dashboard\n\`\`\`\n\n## 我的题目\n\n`;
  const groups=new Map();for(const row of this.rows){const knowledge=this.trees.find(t=>t.kind==='knowledge'&&this.treeMatch(row.q,t))?.nodes||[],chapters=this.trees.find(t=>t.kind==='chapter'&&this.treeMatch(row.q,t))?.nodes||[];const group=groupFolder(row.q,this.names,knowledge,chapters).replaceAll('/',' · ');if(!groups.has(group))groups.set(group,[]);groups.get(group).push(row);}
  for(const [group,rows]of groups){text+=`### ${group}（${rows.length}）\n\n`;for(const {path,q}of rows)text+=`- ${hasImage(q)?'[图] ':''}[[${path.slice(0,-3)}|${cleanTitle(q.title).replace(/[\[\]|]/g,' ')}]] · ${q.type} · ${q.status==='reviewed'?'已核对':'待核对'}\n`;text+='\n';}
  text+='## 我的试卷\n\n'+(this.papers.map(path=>`- [[${path.slice(0,-3)}|${this.paperTitles.get(path)}]]`).join('\n')||'暂无试卷。核对题目后，可交给 Agent 组卷。')+'\n\n原件和图片收在「资料」，备课笔记放在「教学笔记」。\n';
  if(!await this.store.io.exists('题库首页.md')||await this.store.io.read('题库首页.md')!==text)await this.store.io.write('题库首页.md',text);
 }
}
