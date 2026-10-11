import YAML from 'yaml';
import {MetadataCache} from './metadata-cache.js';
import {cleanTitle,nativeTags,enrichQuestion,groupFolder,hasImage} from './presentation.js';
export const BASE='https://tizhuang.qcscience.cc/api';
export const PROPS={schema:'数据格式',id:'题目编号',title:'题目名称',content_format:'正文格式',status:'审核状态',type:'题型',score:'分值',difficulty:'难度',subject_id:'学科编号',phase_id:'学段编号',grade_id:'年级编号',edition_id:'教材版本编号',knowledge_tree_ids:'知识节点编号',knowledge_ids:'精确知识编号',chapter_ids:'教材章节编号',tags:'标签',created_at:'创建时间',updated_at:'更新时间',source_kind:'来源类型',source_provider:'来源平台',source_external_id:'来源题号',source_label:'来源说明'};
const scopeKeys=['subject_id','phase_id','grade_id','edition_id'];
// Legacy batches stored one tree; current batches keep both namespaces separately.
export function directoryNodes(scope,nodes){return Array.isArray(nodes)?(scope.knowledge_tree_id&&!scope.chapter_id?{chapters:[],knowledge:nodes}:{chapters:nodes,knowledge:[]}):{chapters:nodes?.chapters||[],knowledge:nodes?.knowledge||[]};}
export function requireScope(s,nodes){
  for(const k of ['subject_id','phase_id'])if(!Number.isSafeInteger(Number(s[k]))||Number(s[k])<=0)throw Error('请选择学科和学段。');
  for(const k of ['edition_id','grade_id','chapter_id','knowledge_tree_id'])if(s[k]!=null&&s[k]!==''&&(!Number.isSafeInteger(Number(s[k]))||Number(s[k])<=0))throw Error('筛选编号无效，请重新选择。');
  const {chapters,knowledge}=directoryNodes(s,nodes);
  if(s.chapter_id){
    if(!s.edition_id)throw Error('选择章节时需要指定教材版本。');
    const node=chapters.find(n=>String(n.id)===String(s.chapter_id));
    if(!node||['subject_id','phase_id','edition_id'].some(k=>String(node[k])!==String(s[k])))throw Error('章节不属于当前教材，请重新加载目录。');
    if(s.grade_id&&String(node.grade_id)!==String(s.grade_id))throw Error('章节不属于所选年级，请重新选择。');
  }
  if(s.knowledge_tree_id&&!knowledge.some(n=>String(n.id)===String(s.knowledge_tree_id)))throw Error('知识点不属于当前学科学段的知识树。');
}
export function queryFilters(s,nodes){
  requireScope(s,nodes);
  if(s.chapter_id&&s.knowledge_tree_id)throw Error('章节和知识点请选择其中一个，也可以都不选。');
  const filters={};for(const k of ['subject_id','edition_id','grade_id','chapter_id','knowledge_tree_id'])if(s[k])filters[k]=s[k];
  if(!s.chapter_id&&!s.knowledge_tree_id){
    // The existing endpoint has no phase_id filter. All phase roots express the
    // selected school-stage knowledge scope in one request, without paid fan-out.
    const tree=validateKnowledge(directoryNodes(s,nodes).knowledge);
    const roots=tree.filter(n=>!n.parent_id).map(n=>n.id);
    if(!roots.length)throw Error('当前学段的知识目录尚未加载，无法确定取题范围，请重新加载目录。');
    filters.knowledge_tree_ids=roots;
  }
  return filters;
}
export function validateKnowledge(nodes){
  if(!Array.isArray(nodes)||nodes.length>=5000)throw Error('知识树不完整，停止取题。');
  const map=new Map();for(const n of nodes){if(!Number.isSafeInteger(n.id)||n.id<=0||!n.name||map.has(String(n.id)))throw Error('知识树数据不一致。');map.set(String(n.id),n);}
  for(const n of nodes){let p=n;const seen=new Set();while(p){if(seen.has(String(p.id)))throw Error('知识树存在循环。');seen.add(String(p.id));if(p.parent_id&&!map.has(String(p.parent_id)))throw Error('知识树缺少父节点。');p=map.get(String(p.parent_id));}}
  return nodes;
}
export function contextFromProperties(meta,path=''){
  const id=v=>Number.isSafeInteger(Number(v))&&Number(v)>0?Number(v):null;
  if(!meta||!id(meta['学科编号'])||!id(meta['学段编号']))return null;
  const base={subject_id:id(meta['学科编号']),phase_id:id(meta['学段编号'])};
  if(id(meta['章节编号'])&&id(meta['教材版本编号']))return {mode:'chapter',scope:{...base,edition_id:id(meta['教材版本编号']),chapter_id:id(meta['章节编号']),grade_id:id(meta['年级编号'])},path};
  // A question note can contain an array of associations; never guess which one the teacher means.
  if(!Array.isArray(meta['知识节点编号'])&&id(meta['知识节点编号']))return {mode:'knowledge',scope:{...base,knowledge_tree_id:id(meta['知识节点编号'])},path};
  return null;
}
export function cursorKey(s){return JSON.stringify(['subject_id','phase_id','edition_id','chapter_id','grade_id','knowledge_tree_id'].map(k=>s[k]??null));}
export class ApiError extends Error{constructor(message,status,code){super(message);this.status=status;this.code=code;}}
export class RequestTimeout extends Error{}
export async function boundedRequest(transport,request,timeoutMs){
  let timer;try{return await Promise.race([Promise.resolve().then(()=>transport(request)),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new RequestTimeout('request_timeout')),timeoutMs);})]);}finally{clearTimeout(timer);}
}
export function validateChapters(nodes,s){
  if(!Array.isArray(nodes)||nodes.length>=1000) throw Error('教材目录不完整，停止取题。');
  const map=new Map();
  for(const n of nodes){
    if(!Number.isSafeInteger(n.id)||n.id<=0||!n.name||map.has(String(n.id))||['subject_id','phase_id','edition_id'].some(k=>String(n[k])!==String(s[k]))) throw Error('教材目录数据不一致。');
    map.set(String(n.id),n);
  }
  for(const n of nodes){let p=n;const seen=new Set();while(p){if(seen.has(String(p.id))) throw Error('教材目录存在循环。');seen.add(String(p.id));if(p.parent_id && !map.has(String(p.parent_id))) throw Error('教材目录缺少父章节。');p=map.get(String(p.parent_id));}}
  return nodes;
}
export class Api {
  constructor(transport,key,{cache=new MetadataCache(),timeouts={},scopedDirectories=false}={}){this.transport=transport;this.scopedDirectories=scopedDirectories;this.directoryPolicy='unknown';this.key=key;this.cache=cache;this.timeouts={metadata:10000,quota:10000,questions:35000,...timeouts};}
  async get(route,params={},paid=false){
    const protectedRoute=route==='/v1/quota'||route==='/v1/questions'||route.startsWith('/v1/local-bank/meta/')||route==='/v1/local-bank/directory-quota';
    const key=protectedRoute?this.key()?.trim():null;
    if(protectedRoute&&!key) throw Error('请先在插件设置中填写自己的题庄 API Key。');
    const url=new URL(BASE+route);
    for(const [k,v] of Object.entries(params)) if(v!==null&&v!==undefined&&v!=='')for(const item of (Array.isArray(v)?v:[v]))url.searchParams.append(k,String(item));
    const timeout=paid?this.timeouts.questions:route==='/v1/quota'?this.timeouts.quota:this.timeouts.metadata;
    let r;try{r=await boundedRequest(this.transport,{url:url.href,method:'GET',headers:key?{'X-API-Key':key}:{},throw:false},timeout);}catch(error){
      if(error instanceof RequestTimeout)throw new ApiError(paid?'取题等待超时，可能已经扣额。请刷新额度确认后再决定是否重新获取；不会自动重试。':`${route==='/v1/quota'?'额度查询':'目录加载'}超过 ${timeout/1000} 秒，请稍后重试。可以继续切换选择。`,0,'request_timeout');
      throw Error(paid?'取题请求未收到确定结果，可能已经扣额。请刷新额度后再决定是否重新获取。':'网络连接失败，请稍后重试。');
    }
    let code='';try{code=r.json?.detail?.code||r.json?.code||'';}catch{}
    if(code==='directory_scope_limit')throw new ApiError('目录范围额度已用完，请联系管理员增加；已开通的学段和学科可继续使用。',r.status,code);
    if(r.status===401||r.status===403) throw new ApiError('凭证无效或无访问权限，请检查自己的 API Key。',r.status,code);
    if(r.status===429) throw new ApiError(code==='query_concurrency_limit'?'网站正在处理你的另一条查题请求，请稍后手动重试。':'额度不足或请求过于频繁，请刷新额度；不会自动重试。',r.status,code);
    if(r.status<200||r.status>=300){let msg=code==='query_timeout'||r.status===504?'查题超时，网站没有返回题目。':r.status===400||r.status===422?'取题条件无效，请重新加载目录并检查教材、章节。':`网站查询失败（HTTP ${r.status}）。`;throw new ApiError(msg+(paid?' 会刷新额度核对，不会自动重试。':''),r.status,code);}
    try{return r.json;}catch{throw Error(paid?'取题响应无法读取，请先刷新额度确认扣减。':'网站数据无法读取。');}
  }
  async directoryCapabilities(force=false){
    if(force)this.directoryCheck=null;
    if(!this.directoryCheck)this.directoryCheck=(async()=>{try{const data=await this.get('/v1/local-bank/capabilities');if(data?.directory_quota!==true)throw Error('目录额度服务响应无效');this.directoryPolicy='enabled';return true;}catch(error){if(error.status===404){this.directoryPolicy='legacy';return false;}this.directoryCheck=null;throw error;}})();
    return this.directoryCheck;
  }
  async meta(name,params={},options={}){
    const scoped=this.scopedDirectories&&['chapters','knowledge-points'].includes(name);
    const enabled=scoped?await this.directoryCapabilities(options.force):false;
    if(enabled){if(!this.key()?.trim())throw Error('请先设置自己的题庄 API Key。目录按学段和学科开通，每个账号默认 5 个。');
      // Enforce admission before using a disk cache from another account. The
      // protected route retains the server's metadata cache; only the response
      // is local. Existing offline trees remain the teacher's own files.
      return this.get('/v1/local-bank/meta/'+name,params);
    }
    return this.cache.get(name,params,()=>this.get('/v1/meta/'+name,params),options);
  }
  directoryQuota(){return this.get('/v1/local-bank/directory-quota');}
  quota(){return this.get('/v1/quota');}
  async questions(s,nodes,count,options={}){
    const filters=queryFilters(s,nodes);
    if(!Number.isInteger(count)||count<1||count>20) throw Error('每次获取题数须为 1 到 20。');
    const quota=await this.quota();
    options.onQuota?.(quota);
    if(!Number.isFinite(quota.remaining)||quota.remaining<count) throw Error(`今日剩余额度不足 ${count} 题。`);
    const data=await this.get('/v1/questions',{...filters,limit:count,offset:options.offset||0,random_order:false},true);
    if(!data||!Array.isArray(data.items)||data.items.length>count) throw Error('取题响应异常，可能已扣额。请刷新额度确认。');
    return data;
  }
}
export function redacted(raw,solutions){
  const clone=JSON.parse(JSON.stringify(raw));
  function walk(q){if(!solutions)for(const k of ['answer','answer_html','analysis','analysis_html'])q[k]='';for(const c of q.subquestions||[])walk(c);}
  walk(clone);return clone;
}
export function questionFrom(raw,s,solutions,toMarkdown){
  if(raw.id==null || String(raw.subject_id)!==String(s.subject_id))throw Error('返回题目的编号或学科无效；保留结果供核查，不自动保存。');
  const source=redacted(raw,solutions);
  function parts(v){const opts=v.options_html&&Object.keys(v.options_html).length?v.options_html:v.options||{};return [toMarkdown(v.title_html||v.title||'')+Object.entries(opts).map(([k,t])=>'\n\n'+k+'. '+toMarkdown(String(t))).join(''),toMarkdown(v.answer_html||v.answer||''),toMarkdown(v.analysis_html||v.analysis||'')];}
  const [content,answer,analysis]=parts(source);const sections={content,answer,analysis};
  for(const [i,c] of (source.subquestions||[]).entries()){const p=parts(c);for(const [j,k] of ['content','answer','analysis'].entries()) if(p[j])sections[k]+=`\n\n#### （${i+1}）\n\n${p[j]}`;}
  if(!sections.content.trim()||Object.values(sections).some(x=>x.includes('<!-- bank:'))) throw Error('题目正文无效。');
  const now=new Date().toISOString();
  return {schema:'tizhuang.question/v1',id:crypto.randomUUID(),title:cleanTitle(toMarkdown(raw.title||raw.title_html||'网站题目'),raw.question_type||'题目'),...sections,content_format:'markdown',status:'draft',type:raw.question_type||'未分类',score:5,difficulty:raw.difficulty??null,subject_id:Number(s.subject_id),phase_id:Number(s.phase_id),grade_id:raw.grade_id??null,edition_id:s.edition_id?Number(s.edition_id):null,knowledge_tree_ids:s.knowledge_tree_id?[String(s.knowledge_tree_id)]:[],knowledge_ids:[],chapter_ids:s.chapter_id?[String(s.chapter_id)]:[],tags:['网站题目'],source:{kind:'website',provider:'tizhuang',external_id:String(raw.id),label:raw.source||'题庄网站'},assets:[],created_at:now,updated_at:now,original_payload:source};
}
export function noteText(q,assetDir='附件',path='题目库/题目.md'){
  const fields={};for(const [key,value]of Object.entries(q))if(PROPS[key])fields[PROPS[key]]=key==='status'?(value==='reviewed'?'已核对':'待核对'):value;
  for(const k of ['kind','provider','external_id','label'])fields[PROPS['source_'+k]]=q.source[k]||'';
  delete fields['标签'];fields.tags=nativeTags(q.tags);if(q.search_text)fields['检索文字']=q.search_text;
  // PyYAML in the independent skill uses YAML 1.1; quote timestamp-like strings.
  let text='---\n'+YAML.stringify(fields,{version:'1.1'})+'---\n\n';
  const prefix='../'.repeat(path.split('/').length-1)+assetDir+'/';
  for(const [key,label]of [['content','题目'],['answer','答案'],['analysis','解析']])text+=`## ${label}\n\n<!-- bank:${key}:start -->\n${q[key].replaceAll('Assets/',prefix)}\n<!-- bank:${key}:end -->\n\n`;
  return text;
}
export function readNote(text){
  const m=text.match(/^\uFEFF?---\r?\n([\s\S]*?)\r?\n---\r?\n/);if(!m)throw Error('题目文件缺少属性。');
  const fields=YAML.parse(m[1]);const reverse=Object.fromEntries(Object.entries(PROPS).map(([k,v])=>[v,k]));
  const q=Object.fromEntries(Object.entries(fields).map(([k,v])=>[reverse[k]||k,v]));
  q.tags=nativeTags(Object.hasOwn(fields,'tags')?fields.tags:fields['标签']);q.status=({'待核对':'draft','已核对':'reviewed'})[q.status]||q.status||'draft';q.search_text=fields['检索文字']||fields.search_text||'';
  for(const key of ['knowledge_tree_ids','knowledge_ids','chapter_ids'])q[key]=(q[key]||[]).map(String);
  for(const k of ['content','answer','analysis']){const pattern=new RegExp(`<!-- bank:${k}:start -->\\r?\\n([\\s\\S]*?)\\r?\\n<!-- bank:${k}:end -->`,'g');const all=[...text.matchAll(pattern)];if(all.length!==1)throw Error('题目区块标记缺失或重复。');q[k]=all[0][1].replace(/(?:\.\.\/)+(?:资料\/)?(?:附件|Assets)\//g,'Assets/');}
  q.source={kind:q.source_kind,provider:q.source_provider,external_id:String(q.source_external_id||''),label:q.source_label||''};return q;
}
export const safeName=s=>String(s).replace(/[<>:"/\\|?*\x00-\x1f\[\]#^]/g,' ').replace(/\s+/g,' ').trim().replace(/[. ]+$/,'').slice(0,80)||'网站题目';
export async function hash(bytes){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');}
export async function localize(q,transport,document){
  const pending=new Map();const downloaded=[];let total=0;const references=[];
  for(const k of ['content','answer','analysis']){
    // Markdown conversion preserves image URLs. Reject unsupported remote schemes instead of leaving missing images.
    const matches=[...q[k].matchAll(/!\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)/g),...q[k].matchAll(/<img\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi)];
    for(const m of matches){
      let url=m[1];if(document){const el=document.createElement('textarea');el.innerHTML=url;url=el.value;}
      references.push([m[1],url]);if(pending.has(url))continue;
      let u;try{u=new URL(url);}catch{throw Error('图片地址不受支持，停止保存。');}if(u.protocol!=='https:'||u.username||u.password||u.port||/^(localhost|127\.|10\.|192\.168\.|169\.254\.|\[|172\.(1[6-9]|2\d|3[01])\.)/i.test(u.hostname))throw Error('图片地址不受支持，停止保存。');
      let r;try{r=await boundedRequest(transport,{url:u.href,method:'GET',headers:{},throw:false},20000);}catch(error){if(error instanceof RequestTimeout)throw Error('图片下载超过 20 秒，请重试保存，无需重新获取题目。');throw error;}
      const mime=(r.headers['content-type']||r.headers['Content-Type']||'').split(';')[0].toLowerCase();const ext={'image/png':'.png','image/jpeg':'.jpg','image/gif':'.gif','image/webp':'.webp'}[mime];
      if(r.status!==200||!ext||r.arrayBuffer.byteLength>10*1024*1024)throw Error('图片下载失败或格式/大小不受支持，请重试保存。');
      total+=r.arrayBuffer.byteLength;if(total>40*1024*1024)throw Error('单题附件超过 40 MB。');
      const sha=await hash(r.arrayBuffer);const path=`Assets/${sha}${ext}`;pending.set(url,path);downloaded.push({path,sha256:sha,data:r.arrayBuffer});
    }
  }
  // Apply replacements only after every download succeeds: failed saves can reuse the same raw batch.
  const copy=structuredClone(q);for(const k of ['content','answer','analysis'])for(const [original,url]of references)copy[k]=copy[k].replaceAll(original,pending.get(url));
  if(['content','answer','analysis'].some(k=>/!\[[^\]]*\]\((?!Assets\/)/.test(copy[k])))throw Error('题目包含未归档图片，停止保存。');
  copy.assets=downloaded.map(({path,sha256})=>({path,sha256}));return {question:copy,downloaded};
}
export class Store{
  constructor(io){this.io=io;this.busy=false;}
  async mkdir(path){let p='';for(const part of path.split('/')){p=p?`${p}/${part}`:part;if(!await this.io.exists(p))await this.io.mkdir(p);}}
  async init(){
    if(await this.io.exists('Questions'))throw Error('检测到旧版英文题库，请先使用本地 skill 迁移中文目录。');
    if(await this.io.exists('.bank/config.json')){const cfg=JSON.parse(await this.io.read('.bank/config.json'));if(cfg.schema!=='tizhuang.bank/v1')throw Error('本地题库格式不兼容。');}
    const modern=!await this.io.exists('.bank/config.json')||JSON.parse(await this.io.read('.bank/config.json')).ui_layout==='teacher/v2';this.assetDir=modern?'资料/附件':'附件';
    for(const p of ['题目库',this.assetDir,'.bank/records','.bank/textbooks','.bank/taxonomy',modern?'教学笔记':'知识库/我的教学笔记',modern?'资料/教材目录':'教材目录','试卷','待整理'])await this.mkdir(p);
    if(!await this.io.exists('.bank/config.json'))await this.io.write('.bank/config.json',JSON.stringify({schema:'tizhuang.bank/v1',ui_layout:modern?'teacher/v2':'zh-CN/v1',created_at:new Date().toISOString()},null,2));
    if(!modern&&!await this.io.exists('题库入口.md'))await this.io.write('题库入口.md','# 我的教师题库\n\n- [[题目导航|浏览题目]]\n- 使用左侧书库图标打开题库首页。\n- 在 Agent 中使用 tizhuang-local-bank 检索、组卷。\n');
  }
  async files(folder,extension='.md'){if(!await this.io.exists(folder))return [];const listing=await this.io.list(folder);const all=listing.files.filter(p=>p.endsWith(extension));for(const p of listing.folders||[])all.push(...await this.files(p,extension));return [...new Set(all)];}
  async existing(){const rows=[];for(const path of await this.files('题目库'))rows.push({path,q:readNote(await this.io.read(path))});return rows;}
  async json(path,fallback={}){return await this.io.exists(path)?JSON.parse(await this.io.read(path)):fallback;}
  async saveCatalog(data){await this.mkdir('.bank/catalog');const names=await this.json('.bank/catalog/names.json',{subjects:{},phases:{},editions:{}});for(const [key,rows]of Object.entries(data))for(const n of rows)names[key][n.id]=n.name;await this.io.write('.bank/catalog/names.json',JSON.stringify(names));}
  async save(q,nodes,downloads){
    if(this.busy)throw Error('正在保存，请等待完成。');this.busy=true;
    try{
      await this.init();const requested={subject_id:q.subject_id,phase_id:q.phase_id,edition_id:q.edition_id,chapter_id:q.chapter_ids[0],knowledge_tree_id:q.knowledge_tree_ids[0],grade_id:null};const directory=directoryNodes(requested,nodes);requireScope(requested,directory);validateKnowledge(directory.knowledge);validateChapters(directory.chapters,q);
      const rows=await this.existing();for(const old of rows){
        const sameScope=scopeKeys.every(k=>String(old.q[k]??null)===String(q[k]??null));
        if(sameScope&&old.q.content.trim()===q.content.trim())return {action:'duplicate',path:old.path};
        if(old.q.source.provider===q.source.provider&&old.q.source.external_id===q.source.external_id&&old.q.content!==q.content)throw Error('同来源题目正文已有不同版本，请人工处理；不会覆盖本地文件。');
      }
      const tree=(await this.json(`.bank/taxonomy/${q.subject_id}-${q.phase_id}.json`)).nodes||directory.knowledge;enrichQuestion(q,tree);q.title=cleanTitle(q.title,q.type);
      const modern=this.assetDir==='资料/附件';const folder=modern?'题目库/'+groupFolder(q,await this.json('.bank/catalog/names.json'),tree,directory.chapters):'题目库';await this.mkdir(folder);
      const stem=(hasImage(q)?'图 · ':'')+safeName(q.title);let path=`${folder}/${stem}.md`;let suffix=2;while(await this.io.exists(path))path=`${folder}/${stem}（${suffix++}）.md`;
      if(await this.io.exists(`.bank/records/${q.id}.json`))throw Error('来源记录编号冲突，停止保存。');
      for(const a of downloads){if(await hash(a.data)!==a.sha256||a.path!==`Assets/${a.sha256}${a.path.slice(a.path.lastIndexOf('.'))}`)throw Error('附件校验失败。');const local=this.assetDir+'/'+a.path.split('/').pop();if(await this.io.exists(local)){if(await hash(await this.io.readBinary(local))!==a.sha256)throw Error('已有附件损坏。');}else await this.io.writeBinary(local,a.data);}
      for(const [kind,list]of [['knowledge',directory.knowledge],['chapter',directory.chapters]]){
        if(!list.length)continue;const knowledge=kind==='knowledge';
        const snapshot=knowledge?`.bank/taxonomy/${q.subject_id}-${q.phase_id}.json`:`.bank/textbooks/${q.subject_id}-${q.phase_id}-${q.edition_id}.json`;
        // Preserve teacher-owned snapshots; validate selected links in both trees.
        if(await this.io.exists(snapshot)){
          const saved=JSON.parse(await this.io.read(snapshot));if(saved.subject_id!==q.subject_id||saved.phase_id!==q.phase_id)throw Error('已有目录学科学段不一致。');
          if(knowledge)validateKnowledge(saved.nodes);else validateChapters(saved.nodes,q);
          requireScope(requested,{...directory,[knowledge?'knowledge':'chapters']:saved.nodes});
        }else await this.io.write(snapshot,JSON.stringify({schema:knowledge?'tizhuang.taxonomy/v1':'tizhuang.textbook/v1',subject_id:q.subject_id,phase_id:q.phase_id,...(knowledge?{}:{edition_id:q.edition_id}),downloaded_at:new Date().toISOString(),nodes:list},null,2));
      }
      await this.io.write(`.bank/records/${q.id}.json`,JSON.stringify(q,null,2));
      await this.io.write(path,noteText(q,this.assetDir,path));
      rows.push({path,q});
      // Dedicated plugin navigation avoids replacing the skill's/user's existing navigation.
      if(!modern)await this.io.write('网站取题导航.md','# 网站取题导航\n\n'+rows.map(({path,q})=>`- [[${path.slice(0,-3)}|${safeName(q.title)}]]`).join('\n')+'\n');
      return {action:'created',path};
    }finally{this.busy=false;}
  }
}
