import YAML from 'yaml';

// Same mapping and frontmatter contract as the independent skill's ui_layout.py.
const name=value=>{
  let text=String(value).replace(/<[^>]+>/g,'').replace(/[<>:"/\\|?*\[\]#^\x00-\x1f]/g,' ').replace(/\s+/g,' ').replace(/^[ .]+|[ .]+$/g,'').slice(0,55);
  return !text||/^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i.test(text)?'未命名':text;
};
const safePath=path=>typeof path==='string'&&!path.includes('\\')&&!path.includes(':')&&!path.startsWith('/')&&path.split('/').every(p=>p&&p!=='.'&&p!=='..')&&path.endsWith('.md');

export async function materializeKnowledge(store,data){
  const {subject_id:subject,phase_id:phase,nodes}=data,chapter=data.edition_id!=null,kind=chapter?'chapters':'knowledge',scope=`${subject}-${phase}${chapter?'-'+data.edition_id:''}`;
  const modern=(await store.json('.bank/config.json')).ui_layout==='teacher/v2';
  const root=chapter?(modern?'资料/教材目录':'教材目录'):(modern?'资料/知识目录':'知识库/标准知识点');
  const labels=await store.json('.bank/catalog/names.json');
  const title=name(`${labels.phases?.[phase]||`学段${phase}`} · ${labels.subjects?.[subject]||`学科${subject}`}${chapter?' · '+(labels.editions?.[data.edition_id]||`教材版本${data.edition_id}`):''}`);
  const landing=chapter?'教材目录':'知识树';
  const base=`${root}/${title}`,mapping=await store.json('.bank/ui-paths.json',{knowledge:{},chapters:{}});
  mapping.knowledge??={};mapping.chapters??={};
  const paths={...(mapping[kind][scope]||{})},byId=new Map(nodes.map(n=>[String(n.id),n]));
  // Preserve the teacher/skill's existing paths and notes; only create missing files.
  for(const path of Object.values(paths))if(!safePath(path))throw Error('知识目录路径无效，请检查 .bank/ui-paths.json。');
  const reserved=new Set(Object.values(paths));reserved.add(`${base}/${landing}.md`);
  for(const n of nodes){
    const key=String(n.id);if(paths[key])continue;
    const ancestors=[];let parent=byId.get(String(n.parent_id));
    while(parent){ancestors.unshift(name(parent.name));parent=byId.get(String(parent.parent_id));}
    const folder=[base,...ancestors.slice(0,2)].join('/'),stem=name(n.name);
    let path=`${folder}/${stem}.md`,i=2;
    while(reserved.has(path)||await store.io.exists(path))path=`${folder}/${stem}（${i++}）.md`;
    paths[key]=path;reserved.add(path);
  }
  mapping[kind][scope]=paths;
  // Publish stable paths before notes so a failed/partial write retries at the same paths.
  await store.io.write('.bank/ui-paths.json',JSON.stringify(mapping,null,2));
  const link=n=>`[[${paths[String(n.id)].slice(0,-3)}|${name(n.name)}]]`;
  const create=async(path,text)=>{if(await store.io.exists(path))return;await store.mkdir(path.slice(0,path.lastIndexOf('/')));await store.io.write(path,text);};
  const children=new Map();for(const n of nodes){const p=String(n.parent_id);if(!children.has(p))children.set(p,[]);children.get(p).push(n);}
  for(const n of nodes){
    const parent=byId.get(String(n.parent_id));
    const meta={...(chapter?{'章节编号':String(n.id),'教材版本编号':data.edition_id,'年级编号':n.grade_id??null}:{'知识节点编号':String(n.id),'精确知识编号':String(n.knowledge_id||'')}),'学科编号':subject,'学段编号':phase,'内容管理':'系统生成'};
    const personal=modern?'教学笔记':'知识库/我的教学笔记';
    await create(paths[String(n.id)],`---\n${YAML.stringify(meta)}---\n\n# ${n.name}\n\n${parent?'父知识点：'+link(parent)+'\n\n':''}${(children.get(String(n.id))||[]).map(c=>'- '+link(c)).join('\n')}\n\n个人笔记：[[${personal}/${name(n.name)} · ${scope}|我的教学笔记]]\n`);
  }
  await create(`${base}/${landing}.md`,`# ${title}${landing}\n\n共 ${nodes.length} 个${chapter?'章节':'知识点'}。点击分类逐级浏览。\n\n${nodes.filter(n=>!byId.has(String(n.parent_id))).map(n=>'- '+link(n)).join('\n')}\n`);
  return {nodes:nodes.length,path:`${base}/${landing}.md`};
}
