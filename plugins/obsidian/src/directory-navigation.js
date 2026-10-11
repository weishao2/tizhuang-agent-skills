import YAML from 'yaml';
import {contextFromProperties} from './core.js';

const same=(a,b)=>String(a??'')===String(b??'');
const bases={chapter:['资料/教材目录','教材目录'],knowledge:['资料/知识目录','知识库/标准知识点','知识库']};

export async function findDirectoryTarget(plugin,scope,kind,sourcePath=''){
 const {app,store}=plugin,roots=bases[kind];
 if(!roots)throw Error('未知目录类型');
 const paths=app.vault.getMarkdownFiles?app.vault.getMarkdownFiles().map(f=>f.path):(await Promise.all(roots.map(p=>store.files(p)))).flat();
 const listed=new Set(paths),candidates=[...new Set([sourcePath,...paths].filter(p=>p&&p.endsWith('.md')&&!p.startsWith('.')))];
 const nodeId=scope[kind==='chapter'?'chapter_id':'knowledge_tree_id'];let related;
 for(const path of candidates){
   const file=app.vault.getAbstractFileByPath(path);if(!file||(!listed.has(path)&&!await store.io.exists(path)))continue;
   let properties=app.metadataCache.getFileCache(file)?.frontmatter;
   if(!properties&&roots.some(r=>path.startsWith(r+'/'))){
     try{const text=await store.io.read(path),match=text.match(/^\uFEFF?---\r?\n([\s\S]*?)\r?\n---\r?\n/);if(match)properties=YAML.parse(match[1]);}catch{continue;}
   }
   const context=contextFromProperties(properties,path);
   if(context?.mode!==kind||!same(context.scope.subject_id,scope.subject_id)||!same(context.scope.phase_id,scope.phase_id))continue;
   if(kind==='chapter'&&scope.edition_id&&!same(context.scope.edition_id,scope.edition_id))continue;
   if(nodeId&&same(context.scope[kind==='chapter'?'chapter_id':'knowledge_tree_id'],nodeId))return {file,exact:true};
   related??=path;
 }
 // Prefer this subject/textbook's existing landing page, then the global index.
 if(related){const parts=related.split('/');for(let n=parts.length-1;n>0;n--){const candidate=parts.slice(0,n).join('/')+'/'+(kind==='chapter'?'教材目录.md':'知识树.md');if(await store.io.exists(candidate))return {file:app.vault.getAbstractFileByPath(candidate),exact:!nodeId};}}
 for(const base of roots){const path=base+'/'+(kind==='chapter'?'教材导航.md':'知识库导航.md');if(await store.io.exists(path))return {file:app.vault.getAbstractFileByPath(path),exact:!nodeId};}
 throw Error('本地尚未下载这类目录，可先使用下方筛选，或通过本地题库 skill 下载教材／知识树。');
}

export async function openDirectory(plugin,view,kind){
 const {file,exact}=await findDirectoryTarget(plugin,view.scope,kind,view.sourcePath);
 if(!file)throw Error('目录文件已被移动，请刷新后重试。');
 const workspace=plugin.app.workspace;
 plugin.routingDirectory=true;
 try{
   const existing=workspace.getLeavesOfType('markdown').find(leaf=>leaf.view?.file?.path===file.path);
   const leaf=existing||workspace.getLeaf?.('tab');
   if(leaf?.openFile){await leaf.openFile(file,{active:true});await workspace.revealLeaf(leaf);}else await workspace.openLinkText(file.path,'','tab');
   let explorer=workspace.getLeavesOfType('file-explorer')[0];
   if(!explorer&&workspace.getLeftLeaf){explorer=workspace.getLeftLeaf(false);await explorer?.setViewState({type:'file-explorer',active:true});}
   if(explorer){await workspace.revealLeaf(explorer);await explorer.loadIfDeferred?.();
     // The built-in explorer is not part of the public API; retain normal opening
     // when a host version doesn't expose its optional reveal helper.
     if(typeof explorer.view?.revealInFolder==='function')await explorer.view.revealInFolder(file);
   }
   view.say(exact?'已打开左侧目录，当前筛选条件保留。':'该节点尚未下载，已打开本地目录；当前筛选条件保留。');
 }finally{plugin.routingDirectory=false;}
}
