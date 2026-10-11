export const hasImage=q=>/!\[|<img\b/i.test(q.content||'');
export function cleanTitle(value,kind='题目'){
 return String(value||'').replace(/!\[[^\]]*\]\([^\n]*?\)|!\[\[[^\]]+\]\]|<img\b[^>]*>/gi,' ').replace(/!\[[^\]]*\]\([^\n]*$|!\[[^\n]*$/g,' ').replace(/<[^>]+>|https?:\/\/\S+/g,' ').replace(/\\[\[\]()]/g,'').replace(/^网站题目[：:]\s*/,'').replace(/\s+/g,' ').trim().slice(0,55)||`${kind}（见原图）`;
}
export function nativeTags(values){if(typeof values==='string')values=values.split(/[,，\s]+/);return [...new Set((values||[]).map(v=>String(v).trim().replace(/^#+/,'').replace(/[^\p{L}\p{N}_/\-]/gu,'_').replace(/[/_]+$/,'').replace(/^[/_]+/,'').replace(/\/+/g,'/')).filter(Boolean).map(v=>/^\d+$/.test(v)?'标签/'+v:v))];}
export function enrichQuestion(q,nodes=[]){
 q.title=cleanTitle(q.title||q.content,q.type);q.tags=nativeTags(q.tags);q.knowledge_tree_ids=(q.knowledge_tree_ids||[]).map(String);q.knowledge_ids=(q.knowledge_ids||[]).map(String);
 const names=new Map();for(const n of nodes){const key=n.name.trim();names.set(key,[...(names.get(key)||[]),n]);}
 for(const name of typeof q.original_payload?.knowledges==='string'?q.original_payload.knowledges.split(/[,，、]/):[]){const matches=names.get(name.trim())||[];if(matches.length===1&&!q.knowledge_tree_ids.includes(String(matches[0].id)))q.knowledge_tree_ids.push(String(matches[0].id));}
 for(const n of nodes)if(q.knowledge_tree_ids.includes(String(n.id))){q.tags.push('考点/'+n.name);if(n.knowledge_id!=null&&!q.knowledge_ids.includes(String(n.knowledge_id)))q.knowledge_ids.push(String(n.knowledge_id));}q.tags=nativeTags(q.tags);return q;
}
export const fileName=s=>String(s).replace(/[<>:"/\\|?*\x00-\x1f\[\]#^]/g,' ').replace(/\s+/g,' ').trim().replace(/[. ]+$/,'').slice(0,55)||'题目';
export function groupFolder(q,names,knowledge=[],chapters=[]){
 const scope=q.subject_id&&q.phase_id?`${names.phases?.[q.phase_id]||'学段'+q.phase_id} · ${names.subjects?.[q.subject_id]||'学科'+q.subject_id}`:'未指定学科';let group='待分类';
 if(q.knowledge_tree_ids?.length){const map=new Map(knowledge.map(n=>[String(n.id),n]));let n=map.get(String(q.knowledge_tree_ids[0]));const seen=new Set();while(n&&map.has(String(n.parent_id))&&!seen.has(String(n.id))){seen.add(String(n.id));n=map.get(String(n.parent_id));}if(n)group=n.name;}
 else if(q.chapter_ids?.length){const n=chapters.find(n=>String(n.id)===String(q.chapter_ids[0]));if(n)group=(names.editions?.[q.edition_id]||'教材')+' · '+n.name;}
 return fileName(scope)+'/'+fileName(group);
}
