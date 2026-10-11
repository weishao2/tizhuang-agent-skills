// PDF helpers are bundled with this plugin. They do not import another installed skill.
export function runLocal(plugin,command,args=[]){
 if(!['organize','dashboard','pdf-prepare','pdf-import','paper','auto-classify','classify','repair-papers'].includes(command))throw Error('不支持的本地操作');
 if(plugin.localTaskActive||plugin.store.busy)throw Error('正在写入题库，请等待当前操作完成。');
 const base=plugin.app.vault.adapter.getBasePath?.();if(!base)throw Error('本地导入和组卷需要电脑上的本地仓库。');
 const executable=plugin.settings.pythonPath?.trim()||'python';
 const helper=base+'/'+(plugin.manifest.dir||`${plugin.app.vault.configDir||'.obsidian'}/plugins/${plugin.manifest.id}`)+'/helper/local_bank.py';
 plugin.localTaskActive=true;
 return new Promise((resolve,reject)=>{
  const {execFile}=require('child_process');
  execFile(executable,[helper,'--vault',base,command,...args],{windowsHide:true,timeout:120000,maxBuffer:2*1024*1024,encoding:'utf8'},(error,stdout,stderr)=>{
   plugin.localTaskActive=false;let data;try{data=JSON.parse(stdout);}catch{}
   if(data?.ok===false)return reject(Error(data.error));
   if(error)return reject(Error(error.code==='ENOENT'?'未找到 Python。请在插件设置中指定已安装本地题库依赖的 Python 路径。':error.killed?'处理超过 120 秒，已停止；再次执行可继续原 PDF 批次或恢复已生成试卷。':'本地处理未完成。请检查 Python 环境和依赖：'+String(stderr||error.message).slice(-600)));
   if(!data?.ok)return reject(Error('本地工具没有返回有效结果。'));resolve(data.result);
  });
 });
}
