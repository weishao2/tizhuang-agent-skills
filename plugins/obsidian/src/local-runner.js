// PDF helpers are bundled with this plugin. They do not import another installed skill.
const helperPath=(plugin,base,name)=>base+'/'+(plugin.manifest.dir||`${plugin.app.vault.configDir||'.obsidian'}/plugins/${plugin.manifest.id}`)+'/helper/'+name;
export function runLocal(plugin,command,args=[]){
 if(!['organize','dashboard','pdf-prepare','pdf-import','paper','auto-classify','classify','repair-papers','review'].includes(command))throw Error('不支持的本地操作');
 if(plugin.localTaskActive||plugin.store.busy)throw Error('正在写入题库，请等待当前操作完成。');
 const base=plugin.app.vault.adapter.getBasePath?.();if(!base)throw Error('本地导入和组卷需要电脑上的本地仓库。');
 const executable=plugin.settings.pythonPath?.trim()||'python';
 const helper=helperPath(plugin,base,'local_bank.py');
 plugin.localTaskActive=true;
 return new Promise((resolve,reject)=>{
  const {execFile}=require('child_process');
  // On Windows the bare `python` is often the Store stub or absent while the `py` launcher works; try it once, only when the teacher has not chosen a Python.
  const attempt=(file,prefix,fallback)=>execFile(file,[...prefix,helper,'--vault',base,command,...args],{windowsHide:true,timeout:120000,maxBuffer:2*1024*1024,encoding:'utf8'},(error,stdout,stderr)=>{
   if(error?.code==='ENOENT'&&fallback)return attempt(...fallback);
   plugin.localTaskActive=false;let data;try{data=JSON.parse(stdout);}catch{}
   if(data?.kind==='missing_dependency')return reject(Error(explainFailure(null,'ModuleNotFoundError '+data.error)));
   if(data?.ok===false)return reject(Error(data.error+(data.hint?'（'+data.hint+'）':'')));
   if(error)return reject(Error(explainFailure(error,stderr)));
   if(!data?.ok)return reject(Error('本地工具没有返回有效结果。'));resolve(data.result);
  });
  const chosen=plugin.settings.pythonPath?.trim();
  attempt(executable,[],!chosen&&process.platform==='win32'?['py',['-3'],null]:null);
 });
}

// Turn a failed child process into one sentence the teacher can act on.
export function explainFailure(error,stderr=''){
 const text=String(stderr||error?.message||'');
 if(error?.code==='ENOENT')return '未找到 Python。请安装 Python 3.10 或更新版本，并在插件设置里填写它的路径（需已安装本地题库依赖）。';
 if(error?.killed)return '处理超过 120 秒，已停止；再次执行可继续原 PDF 批次或恢复已生成试卷。';
 if(/ModuleNotFoundError|ImportError|No module named/.test(text))return '这个 Python 缺少题库依赖。请在终端运行：python -m pip install -r \"<插件目录>/helper/requirements.txt\"，或让 Agent 运行本地题库的环境检查。';
 if(/SyntaxError/.test(text))return 'Python 版本过低，需要 3.10 或更新版本。';
 return '本地处理未完成。请检查 Python 环境和依赖：'+text.slice(-600);
}

// One-click environment check: find a Python that works, report what is missing, and give a copy-ready fix.
// `exec` is injectable so the logic is testable without spawning processes.
export function pythonCandidates(configured,platform=process.platform){
 if(configured?.trim())return [{label:configured.trim(),file:configured.trim(),prefix:[]}];
 return platform==='win32'?[{label:'python',file:'python',prefix:[]},{label:'py -3',file:'py',prefix:['-3']}]:[{label:'python3',file:'python3',prefix:[]},{label:'python',file:'python',prefix:[]}];
}
export async function checkEnvironment(plugin,exec){
 const base=plugin.app.vault.adapter.getBasePath?.();if(!base)return {ok:false,tried:[],summary:'需要电脑上的本地仓库才能检查环境。'};
 const run=exec||((file,args)=>new Promise(resolve=>require('child_process').execFile(file,args,{windowsHide:true,timeout:30000,maxBuffer:1024*1024,encoding:'utf8'},(error,stdout,stderr)=>resolve({error,stdout,stderr}))));
 const script=helperPath(plugin,base,'doctor.py'),tried=[];
 for(const c of pythonCandidates(plugin.settings.pythonPath)){
  const {error,stdout,stderr}=await run(c.file,[...c.prefix,script,'--vault',base]);let data=null;try{data=JSON.parse(stdout);}catch{}
  // Distinguish "not installed" from "installed but timed out" from "ran but crashed": each needs different advice.
  if(!data){const state=error?.code==='ENOENT'?'missing':(error?.killed||error?.signal||error?.code==='ETIMEDOUT')?'timeout':'broken';tried.push({label:c.label,state,found:state!=='missing',ok:false,checks:[],fix:'',detail:String(stderr||error?.message||'').trim().slice(-300)});continue;}
  const failed=(data.checks||[]).filter(x=>!x.ok);
  tried.push({label:c.label,state:data.ok?'ok':'problem',found:true,ok:Boolean(data.ok),python:data.python,checks:data.checks||[],fix:failed.map(x=>x.fix).filter(Boolean).join('\n'),status:data.status?.result||null});
  if(data.ok)break;
 }
 const good=tried.find(t=>t.ok),seen=tried.find(t=>t.state==='problem');
 return {ok:Boolean(good),python:good?.python||seen?.python||null,tried,fix:good?'':(seen?.fix||''),summary:describeEnvironment(tried)};
}
export function describeEnvironment(tried){
 const good=tried.find(t=>t.ok);
 if(good)return `环境正常：Python 与题库依赖都已就绪（${good.python}）。`;
 const seen=tried.find(t=>t.state==='problem');
 if(seen){const bad=seen.checks.filter(c=>!c.ok).map(c=>`${c.name}：${c.detail||'未通过'}`);return `找到了 Python（${seen.python}），但还有问题：${bad.join('；')}。`;}
 const slow=tried.find(t=>t.state==='timeout');
 if(slow)return `Python（${slow.label}）已安装，但检查超过 30 秒没有响应，可能是杀毒软件在扫描或题库目录在网盘同步。请稍等一会儿再点“检查环境”，不需要重新安装 Python。`;
 const broken=tried.find(t=>t.state==='broken');
 if(broken)return `Python（${broken.label}）已安装，但检查脚本没有正常运行${broken.detail?'：'+broken.detail:''}。请确认插件文件完整（可重新安装插件），不需要重装 Python。`;
 return '没有找到 Python。请安装 Python 3.10 或更新版本（安装时勾选“Add to PATH”），再回来检查；或在上方填写 Python 的完整路径。';
}
