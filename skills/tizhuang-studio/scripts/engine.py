"""One transactional workspace for the browser and Agent. No Obsidian dependency."""
import copy, hashlib, html, json, math, os, re, shutil, sqlite3, threading, time, uuid
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode, urlparse
from urllib.error import HTTPError, URLError
from lxml import html as dom
import content, library, papers

ROOT=Path(__file__).resolve().parents[1]
API='https://tizhuang.qcscience.cc/api'
VERSION='1.0.0'

class StudioError(Exception):
    def __init__(self,message,status=400):
        super().__init__(message); self.status=status

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise StudioError('服务返回了跳转，已停止请求。')

def download(url, key='', limit=8*1024*1024):
    req=Request(url,headers={'Accept':'application/json','User-Agent':'Tizhuang-Studio/0.1',**({'X-API-Key':key} if key else {})})
    try:
        with build_opener(NoRedirect).open(req,timeout=35) as response:
            data=response.read(limit+1)
            if len(data)>limit: raise StudioError('响应过大，已停止。')
            return data
    except HTTPError as e:
        # Do not echo arbitrary upstream content, which can include secrets.
        messages={401:'Key 无效或已失效，请重新设置。',403:'当前账号无权访问该范围，或团队服务不可用。',429:'额度不足或请求过于频繁，请查看额度后再试。'}
        raise StudioError(messages.get(e.code,f'题庄服务返回 {e.code}，请稍后检查。'),e.code) from None
    except (URLError,TimeoutError,OSError):
        raise StudioError('连接未完成；取题可能已扣额。请先刷新额度，不会自动重试。',502) from None

class Service:
    def __init__(self,key=''): self.key=key
    def get(self,path,params=None,protected=False):
        if protected and not self.key: raise StudioError('请在连接设置中填写自己的题庄 Key。')
        query=urlencode({k:v for k,v in (params or {}).items() if v not in (None,'',[])},doseq=True)
        return json.loads(download(API+path+('?' + query if query else ''),self.key if protected else ''))
    def meta(self,name,params):
        if name not in ['subjects','phases','editions','grades','chapters','knowledge-points']: raise StudioError('目录类型无效。')
        protected=name in ['chapters','knowledge-points']
        return self.get(('/v1/local-bank/meta/' if protected else '/v1/meta/')+name,params,protected)
    def quota(self): return self.get('/v1/quota',protected=True)

def number(value,minimum,maximum,integer=False):
    if isinstance(value,bool) or value in ('',None): raise StudioError('请输入有效数字。')
    try: n=float(value)
    except (ValueError,TypeError): raise StudioError('请输入有效数字。') from None
    if not math.isfinite(n) or not minimum<=n<=maximum or (integer and n!=int(n)): raise StudioError(f'数值须在 {minimum}–{maximum} 之间。')
    return int(n) if integer else round(n,2)

def fetch_scope_key(scope):
    fields=('subject_id','phase_id','edition_id','grade_id','chapter_id','knowledge_tree_id','keyword')
    return json.dumps([str(scope.get(k) or '') for k in fields],ensure_ascii=False,separators=(',',':'))

def prepare(raw,root):
    """Freeze original text and local image bytes before showing or exporting."""
    q=copy.deepcopy(raw); q['assets']=[]
    for key in ['content','answer','analysis']:
        text=q.get(key,'') or ''
        # Protect LaTeX before parsing HTML: literal < in formulas must survive.
        formulas={}
        def mask(m):
            t='STUDIOFORMULA'+uuid.uuid4().hex.upper(); formulas[t]=m[0]; return t
        text=re.sub(r'\\\(.+?\\\)|\\\[.+?\\\]|\$\$.+?\$\$|(?<!\\)\$[^$\n]+\$',mask,text,flags=re.S)
        node=dom.fragment_fromstring(text or '<span></span>',create_parent='div')
        for img in node.xpath('.//img'):
            source=img.get('src',''); source=html.unescape(source)
            if source.startswith('Assets/'):
                path=content.asset_path(root,source); data=path.read_bytes()
            else:
                u=urlparse(source)
                if u.scheme!='https' or u.hostname not in ['tizhaung.tos-cn-beijing.volces.com','tizhuang.qcscience.cc'] or u.port not in (None,443) or u.username or u.password:
                    raise StudioError('题图地址未获支持，原始结果已保留，请联系维护者。')
                data=download(source,limit=10*1024*1024)
                from PIL import Image
                from io import BytesIO
                with Image.open(BytesIO(data)) as image:
                    image.verify(); ext={'PNG':'png','JPEG':'jpg','GIF':'gif','WEBP':'webp'}.get(image.format)
                if not ext: raise StudioError('不支持的题图格式。')
                source='Assets/'+content.digest(data)+'.'+ext
                path=content.asset_path(root,source); path.parent.mkdir(exist_ok=True); path.write_bytes(data)
            img.set('src',source)
            q['assets'].append({'path':source,'sha256':content.digest(data)})
        text=dom.tostring(node,encoding='unicode')
        for token,formula in formulas.items(): text=text.replace(token,formula)
        q[key]=content.render(text,'html')
    q['content_format']='html'; q.pop('prepare_error',None)
    return q

def normalize(raw,scope):
    if raw.get('id') is None or str(raw.get('subject_id'))!=str(scope['subject_id']): raise StudioError('取题返回了不同学科，已保留原始结果，请核查。')
    def parts(v):
        opts=v.get('options_html') or v.get('options') or {}
        body=v.get('title_html') or v.get('title') or ''
        body+=''.join('<p>'+html.escape(str(k))+'. '+str(t)+'</p>' for k,t in opts.items())
        fields=[body,v.get('answer_html') or v.get('answer') or '',v.get('analysis_html') or v.get('analysis') or '']
        for i,child in enumerate(v.get('subquestions') or []):
            for j,part in enumerate(parts(child)):
                if part: fields[j]+=f'<p>（{i+1}）</p>'+part
        return fields
    fields=parts(raw)
    return dict(id=str(raw['id']),content=fields[0],answer=fields[1],analysis=fields[2],type=raw.get('question_type','题目'),difficulty=raw.get('difficulty'),knowledge=raw.get('knowledges',''),source={'external_id':str(raw['id']),'label':raw.get('source',''),'year':raw.get('year'),'area':raw.get('area')},subject_id=int(scope['subject_id']),phase_id=int(scope['phase_id']),demo=False)

class Workspace:
    def __init__(self,root,service=None):
        self.paper_summaries={}
        self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'studio.sqlite3'; self.lock=threading.RLock(); self.service=service or Service(os.environ.get('QUESTION_SERVICE_LICENSE',''))
        with self.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY,data TEXT); CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY,data TEXT); CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,data TEXT);')
            db.execute('INSERT OR IGNORE INTO state VALUES(1,?)',(json.dumps({'revision':0,'title':'我的练习卷','duration_minutes':45,'answer_space_mm':20,'items':[],'updated_by':'界面','exports':[]}),))
            stored=json.loads(db.execute('SELECT data FROM state WHERE id=1').fetchone()[0]);changed=False
            for e in stored['exports']:
                if 'question_ids' not in e and re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{8}',e['id']):
                    snapshot=self.root/'exports'/e['id']/'snapshot.json'
                    if snapshot.is_file():
                        try:e['question_ids']=[i['question']['id'] for i in json.loads(snapshot.read_text(encoding='utf-8'))['items']];changed=True
                        except (KeyError,ValueError,TypeError):pass
            if changed:db.execute('UPDATE state SET data=? WHERE id=1',(json.dumps(stored,ensure_ascii=False),))
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db,timeout=15)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            with db: yield db
        finally: db.close()
    def state(self):
        with self.connect() as db:
            s=json.loads(db.execute('SELECT data FROM state WHERE id=1').fetchone()[0])
            s['questions']=[json.loads(r[0]) for r in db.execute('SELECT data FROM questions ORDER BY rowid DESC')]
        s['questions']=[library.decorate(q) for q in s['questions']]
        for e in s['exports']:
            if e['id'] not in self.paper_summaries:
                self.paper_summaries[e['id']]=papers.summary(self.root,e['id'])
            e.update(self.paper_summaries[e['id']])
        s.setdefault('catalogs',[]);s.setdefault('pdf_batches',[])
        s['library_stats']=library.stats(s)
        s['total_score']=round(sum(i['score'] for i in s['items']),2)
        s['connected']=bool(self.service.key); s['version']=VERSION; s['workspace']=str(self.root)
        return s
    def operation(self,body):
        opid=body.get('request_id')
        if not isinstance(opid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}',opid): raise StudioError('缺少有效的操作编号。')
        with self.lock:
            with self.connect() as db:
                old=db.execute('SELECT data FROM operations WHERE id=?',(opid,)).fetchone()
                if old:
                    result=json.loads(old[0])
                    if result.get('pending'): raise StudioError('该操作中断或结果未知，请检查组卷篮/额度后再操作。',409)
                    if 'error' in result: raise StudioError(result['error'],result.get('status',400))
                    return result
                state=json.loads(db.execute('SELECT data FROM state WHERE id=1').fetchone()[0])
                if body.get('revision')!=state['revision']: raise StudioError('组卷篮刚被另一个窗口或 Agent 更新。已刷新，请重做本次操作。',409)
                db.execute('INSERT INTO operations VALUES(?,?)',(opid,json.dumps({'pending':True})))
            try:
                result=self.apply(body,state)
            except Exception as e:
                message=str(e) if isinstance(e,(StudioError,ValueError)) else '处理失败；原始数据已保留，请查看环境和题目附件。'
                with self.connect() as db: db.execute('UPDATE operations SET data=? WHERE id=?',(json.dumps({'error':message,'status':getattr(e,'status',400)}),opid))
                raise StudioError(message,getattr(e,'status',400)) from None
            with self.connect() as db: db.execute('UPDATE operations SET data=? WHERE id=?',(json.dumps(result,ensure_ascii=False),opid))
            return result
    def apply(self,b,s):
        action=b.get('action'); by='Agent' if b.get('actor')=='Agent' else '界面'
        pending_questions=[]; import_result={}
        questions={q['id']:q for q in self.state()['questions']}
        if action=='add':
            ids=b.get('ids',[])
            if not isinstance(ids,list) or not ids: raise StudioError('请先选择题目。')
            for id in ids:
                if id not in questions: raise StudioError('题目不存在，请先找题。')
                if questions[id].get('prepare_error'): raise StudioError('题目尚未完整加载，请先重载附件。')
                if not any(i['id']==id for i in s['items']): s['items'].append({'id':id,'score':5})
            if len(s['items'])>200: raise StudioError('每卷最多 200 题。')
        elif action=='remove': s['items']=[i for i in s['items'] if i['id']!=b.get('id')]
        elif action=='move':
            index=next((n for n,i in enumerate(s['items']) if i['id']==b.get('id')),None)
            if index is None: raise StudioError('题目不在组卷篮中。')
            pos=number(b.get('position'),1,len(s['items']),True)-1
            s['items'].insert(pos,s['items'].pop(index))
        elif action=='score':
            item=next((i for i in s['items'] if i['id']==b.get('id')),None)
            if item is None: raise StudioError('题目不在组卷篮中。')
            item['score']=number(b.get('score'),0,1000)
        elif action=='settings':
            if 'title' in b:
                title=str(b['title']).strip()
                if not title or len(title)>120: raise StudioError('试卷标题须为 1–120 字。')
                s['title']=title
            for field,lo,hi in [('duration_minutes',1,600),('answer_space_mm',0,100)]:
                if field in b: s[field]=number(b[field],lo,hi,True)
        elif action in ('paper-update','paper-open'):
            papers.apply(self.root,b,s,questions,number)
        elif action=='demo':
            for q in json.loads((ROOT/'assets/demo/questions.json').read_text(encoding='utf-8')):
                if q['id'] in questions:continue
                for a in q['assets']:
                    dest=content.asset_path(self.root,a['path']); dest.parent.mkdir(exist_ok=True)
                    shutil.copyfile(ROOT/'assets/demo'/a['path'],dest)
                q['knowledge']=q.get('title','')
                self.save_question(prepare(q,self.root))
        elif action=='retry-prepare':
            path=self.root/'raw'/f"{b.get('id')}.json"
            if not re.fullmatch(r'\d+',str(b.get('id',''))) or not path.is_file(): raise StudioError('没有可重载的原题。')
            previous=questions.get(str(b['id']),{})
            if not previous.get('prepare_error'):raise StudioError('题目附件已完整，不需要重载。')
            q=prepare(json.loads(path.read_text(encoding='utf-8')),self.root)
            for key in ['knowledge_tree_ids','chapter_ids','tags','edition_id','grade_id','notes','title','created_at']:
                if key in previous:q[key]=previous[key]
            q['status']='draft';self.save_question(q)
        elif action=='fetch': import_result=self.fetch(b,s)
        elif action=='import-mcp':
            pending_questions,import_result=self.import_mcp(b,s,questions)
        elif action=='export':
            if not s['items']: raise StudioError('请先选题加入组卷篮。')
            manifest={'title':s['title'],'duration_minutes':s['duration_minutes'],'answer_space_mm':s['answer_space_mm'],'total_score':sum(i['score'] for i in s['items']),'revision':s['revision'],'items':[]}
            for n,i in enumerate(s['items']):
                q=questions.get(i['id'])
                if not q or q.get('prepare_error'): raise StudioError('题目缺失或尚未完整加载，不能导出。')
                if q.get('mcp',{}).get('solutions_status')=='not_returned':
                    raise StudioError('本卷含 MCP 未返回答案的题目，无法生成教师答案版。请让 Agent 明确请求 include_solutions=true 后补充导入；工作台不会自动再次取题。')
                if q.get('status')!='reviewed':raise StudioError('本卷有待核对题目，请先在我的题库查看题干、答案和配图并标记已核对。')
                manifest['items'].append({'number':n+1,'score':i['score'],'question':q})
            from paper_layout import grouped_manifest
            manifest=grouped_manifest(manifest)
            from word_export import export_docx
            ident=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
            folder=self.root/'exports'/ident; folder.mkdir(parents=True)
            try:
                for teacher,name in [(False,'student.docx'),(True,'teacher.docx')]:
                    export_docx(SimpleNamespace(root=self.root),manifest,folder/name,teacher,s['answer_space_mm'])
                    (folder/name.replace('.docx','.html')).write_text(library.print_html(self.root,manifest,teacher),encoding='utf-8')
                (folder/'snapshot.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception:
                # Failed export is never advertised as a complete pair.
                raise
            s['exports'].insert(0,{'id':ident,'title':s['title'],'revision':s['revision'],'count':len(s['items']),'question_ids':[i['id'] for i in s['items']],'created_at':time.strftime('%Y-%m-%d %H:%M'),'student':'/exports/'+ident+'/student.docx','teacher':'/exports/'+ident+'/teacher.docx','student_html':'/exports/'+ident+'/student.html','teacher_html':'/exports/'+ident+'/teacher.html'})
            parent=next((e for e in s['exports'] if e['id']==s.get('editing_paper_id')),None)
            if parent:
                s['exports'][0].update(tags=list(parent.get('tags',[])),source_paper_id=parent['id'])
        else:
            pending_questions,import_result=library.apply(self,b,s,questions)
        s['revision']+=1; s['updated_by']=by; s['updated_at']=time.strftime('%H:%M:%S')
        with self.connect() as db:
            if import_result.pop('replace_all_questions',False):db.execute('DELETE FROM questions')
            for q in pending_questions:
                db.execute('INSERT OR REPLACE INTO questions VALUES(?,?)',(q['id'],json.dumps(q,ensure_ascii=False)))
            db.execute('UPDATE state SET data=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
        return {'ok':True,'revision':s['revision'],**import_result}

    def import_mcp(self,b,s,existing):
        from mcp_import import validate,has_solutions
        scope={k:number(b.get(k),1,100000000,True) for k in ['subject_id','phase_id']}
        rows=validate(b,scope)  # Validate the entire batch before any downloads or writes.
        pending=[]; originals=[]
        report={key:[] for key in ['imported_ids','existing_ids','updated_ids','failed_ids','added_ids','solutions_missing_ids']}
        for raw in rows:
            ident=raw['id']; previous=existing.get(ident)
            if previous and (previous.get('subject_id')!=scope['subject_id'] or previous.get('phase_id')!=scope['phase_id']):
                raise StudioError('已有同题号的学科或学段不同，整批未保存，请核对范围。')
            if previous and not previous.get('prepare_error') and previous.get('mcp',{}).get('solutions_status')!='not_returned':
                report['existing_ids'].append(ident)
                continue  # Never replace complete local questions, answers or scores.
            q=normalize(raw,scope)
            library.associate(q,raw,s.get('catalogs',[]))
            q['mcp']={'auth_mode':b['auth_mode'],'tool':b['tool'],'imported_at':time.strftime('%Y-%m-%d %H:%M:%S'),
                      'solutions_status':'included' if has_solutions(raw) else 'not_returned'}
            original=copy.deepcopy(q)
            try: q=prepare(q,self.root)
            except Exception:
                q['prepare_error']='MCP 题目附件尚未完整保存，可重载附件，无需重新取题。'
                q['assets']=[]
                for key in ['content','answer','analysis']: q[key]=html.escape(q[key])
                report['failed_ids'].append(ident)
            if previous and not previous.get('prepare_error'):
                if q.get('prepare_error') or q['content']!=previous['content']:
                    raise StudioError('补充答案的题干与已存原题不同或附件不完整，整批未保存。')
                if q['mcp']['solutions_status']=='not_returned':
                    report['existing_ids'].append(ident); continue
            pending.append(q); originals.append(original)
            report['updated_ids' if previous else 'imported_ids'].append(ident)
        if pending:
            classified,_=library.apply(self,{'action':'auto-classify','ids':[q['id'] for q in pending]},copy.deepcopy(s),{q['id']:q for q in pending})
            mapped={q['id']:q for q in classified};pending=[mapped.get(q['id'],q) for q in pending]
        available={**existing,**{q['id']:q for q in pending}}
        for raw in rows:
            ident=raw['id']; q=available[ident]
            if q.get('mcp',{}).get('solutions_status')=='not_returned': report['solutions_missing_ids'].append(ident)
            if b.get('add_to_basket') and not q.get('prepare_error') and not any(i['id']==ident for i in s['items']):
                s['items'].append({'id':ident,'score':5}); report['added_ids'].append(ident)
        if len(s['items'])>200: raise StudioError('每卷最多 200 题，整批未保存。')
        if originals:
            rawdir=self.root/'raw'; rawdir.mkdir(exist_ok=True)
            for q in originals:
                (rawdir/(q['id']+'.json')).write_text(json.dumps(q,ensure_ascii=False),encoding='utf-8')
        report['message']='MCP 题目已保存在当前工作台；导入不调用取题接口、不另扣取题额度。'
        return pending,report
    def save_question(self,q):
        with self.connect() as db: db.execute('INSERT OR REPLACE INTO questions VALUES(?,?)',(q['id'],json.dumps(q,ensure_ascii=False)))
    def fetch(self,b,s=None):
        scope={k:number(b.get(k),1,100000000,True) for k in ['subject_id','phase_id']}
        count=number(b.get('count',5),1,20,True)
        if b.get('chapter_id') and b.get('knowledge_tree_id'): raise StudioError('章节和知识点只能选一项。')
        cursor_key=fetch_scope_key(b)
        offset=number(b.get('offset',(s or {}).get('fetch_cursors',{}).get(cursor_key,0)),0,10000,True)
        params={'subject_id':scope['subject_id'],'limit':count,'offset':offset,'random_order':'false'}
        for k in ['edition_id','grade_id','chapter_id']:
            if b.get(k): params[k]=number(b[k],1,100000000,True)
        if b.get('keyword'): params['keyword']=str(b['keyword'])[:100]
        if b.get('chapter_id'):
            if not b.get('edition_id'): raise StudioError('按章节取题须选择教材。')
            nodes=self.fetch_catalog('chapter',scope,s,params['edition_id'])
            if not any(str(n['id'])==str(params['chapter_id']) for n in nodes): raise StudioError('章节不在当前目录中。')
        else:
            nodes=self.fetch_catalog('knowledge',scope,s)
            if not isinstance(nodes,list) or not nodes: raise StudioError('当前学段知识目录为空，已停止取题。')
            chosen=b.get('knowledge_tree_id')
            if chosen and not any(str(n['id'])==str(chosen) for n in nodes): raise StudioError('知识点不在当前学段目录中。')
            params['knowledge_tree_ids']=[str(chosen)] if chosen else [str(n['id']) for n in nodes if not n.get('parent_id')]
            if not params['knowledge_tree_ids']: raise StudioError('目录缺少根节点，已停止取题。')
        quota=self.service.quota()
        if s is not None:
            kind='chapter' if b.get('chapter_id') else 'knowledge'
            c=library.catalog({**scope,'edition_id':b.get('edition_id'),'kind':kind,'nodes':nodes})
            s.setdefault('catalogs',[])
            if not any(x['id']==c['id'] for x in s['catalogs']):s['catalogs'].append(c)
        remain=min(quota.get('remaining',0),quota.get('member_remaining') if quota.get('member_remaining') is not None else quota.get('remaining',0))
        if remain<count: raise StudioError(f'当前可用额度 {remain} 题，不足 {count} 题。')
        result=self.service.get('/v1/questions',params,True)
        rawdir=self.root/'raw'; rawdir.mkdir(exist_ok=True)
        (rawdir/(uuid.uuid4().hex+'-batch.json')).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        if not isinstance(result,dict) or not isinstance(result.get('items'),list) or len(result['items'])>count: raise StudioError('取题响应异常，原始结果已保留；请先核对额度。')
        for raw in result['items']:
            q=normalize(raw,scope)
            if s is not None:library.associate(q,raw,s['catalogs'],b)
            if not re.fullmatch(r'\d+',q['id']): raise StudioError('题号格式异常，原始结果已保留。')
            (rawdir/(q['id']+'.json')).write_text(json.dumps(q,ensure_ascii=False),encoding='utf-8')
            try: q=prepare(q,self.root)
            except Exception as e:
                q['prepare_error']='图片或公式尚未加载完整，可重载附件，无需重新取题。'
                q['assets']=[]
                for k in ['content','answer','analysis']: q[k]=html.escape(q[k])
            # Repeated retrieval must not overwrite a teacher's edits or review state.
            with self.connect() as db:existing=db.execute('SELECT data FROM questions WHERE id=?',(q['id'],)).fetchone()
            if not existing:self.save_question(library.decorate(q))
        next_offset=offset+len(result['items'])
        if s is not None:s.setdefault('fetch_cursors',{})[cursor_key]=next_offset
        return {'fetched_count':len(result['items']),'next_offset':next_offset}

    def fetch_catalog(self,kind,scope,state,edition=None):
        cached=next((c for c in (state or {}).get('catalogs',[])
                     if library.matching(c,{**scope,'edition_id':edition},kind)),None)
        if cached:
            # Never let another account's disk cache stand in for its entitlement.
            quota=self.service.get('/v1/local-bank/directory-quota',protected=True)
            if not isinstance(quota,dict) or not isinstance(quota.get('scopes'),list):
                raise StudioError('目录名额响应异常，请先检查连接；本次未取题。')
            if any(str(x.get('subject_id'))==str(scope['subject_id']) and str(x.get('phase_id'))==str(scope['phase_id']) for x in quota['scopes']):
                return library.catalog(cached)['nodes']
        return self.service.meta('chapters' if kind=='chapter' else 'knowledge-points',
                                 {**scope,**({'edition_id':edition} if edition else {}),'limit':5000})
