const TTL=24*60*60*1000;
const publicNames=new Set(['subjects','phases','grades','editions','chapters','knowledge-points']);
const canonical=(name,params)=>JSON.stringify([name,Object.entries(params).filter(([,v])=>v!=null&&v!=='').map(([k,v])=>[k,String(v)]).sort(([a],[b])=>a.localeCompare(b))]);

// Public directory data only. Quotas, paid questions and credentials never enter this cache.
export class MetadataCache{
  constructor(io=null,{now=()=>Date.now(),ttl=TTL}={}){this.io=io;this.now=now;this.ttl=ttl;this.entries=new Map();this.pending=new Map();this.writes=Promise.resolve();}
  fresh(entry){return entry?.schema==='tizhuang.metadata-cache/v1'&&Array.isArray(entry.data)&&Number.isFinite(entry.fetched_at)&&entry.fetched_at<=this.now()&&this.now()-entry.fetched_at<this.ttl;}
  async path(key){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(key));return '.bank/cache/'+Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('')+'.json';}
  seed(name,params,data,date){const key=canonical(name,params),entry={schema:'tizhuang.metadata-cache/v1',key,data,fetched_at:Date.parse(date)};if(this.fresh(entry)&&!this.fresh(this.entries.get(key)))this.entries.set(key,entry);}
  async get(name,params,loader,{force=false}={}){
    if(!publicNames.has(name))return loader();
    const key=canonical(name,params);
    if(!force&&this.fresh(this.entries.get(key)))return structuredClone(this.entries.get(key).data);
    if(this.pending.has(key))return structuredClone(await this.pending.get(key));
    const load=async()=>{
      let path;
      if(this.io){path=await this.path(key);if(!force)try{
        if(await this.io.exists(path)){const saved=JSON.parse(await this.io.read(path));if(saved.key===key&&this.fresh(saved)){this.entries.set(key,saved);return saved.data;}}
      }catch{/* A corrupt/expired cache is replaceable public data. */}}
      const data=await loader();if(!Array.isArray(data))throw Error('目录响应格式异常，请重新加载目录。');
      const entry={schema:'tizhuang.metadata-cache/v1',key,fetched_at:this.now(),data:structuredClone(data)};
      this.entries.set(key,entry);if(this.entries.size>48)this.entries.delete(this.entries.keys().next().value);
      if(this.io){this.writes=this.writes.catch(()=>{}).then(async()=>{for(const directory of ['.bank','.bank/cache'])if(!await this.io.exists(directory))await this.io.mkdir(directory);await this.io.write(path,JSON.stringify(entry));});try{await this.writes;}catch{/* In-memory caching still works when the vault is read-only. */}}
      return data;
    };
    const work=load();this.pending.set(key,work);try{return structuredClone(await work);}finally{this.pending.delete(key);}
  }
}
