"""Standalone library features for Studio; never opens an Obsidian vault."""
import base64,copy,hashlib,html,json,re,time,uuid,zipfile
from io import BytesIO
from pathlib import Path
import content
from lxml import html as dom

def associate(q,raw,catalogs,scope=None):
    scope=scope or {};q.update({k:int(scope[k]) for k in ['edition_id','grade_id'] if scope.get(k)})
    if isinstance(q.get('knowledge'),list):q['knowledge']='、'.join(str(v.get('name','') if isinstance(v,dict) else v) for v in q['knowledge'])
    for kind,field,selected in [('knowledge','knowledge_tree_ids','knowledge_tree_id'),('chapter','chapter_ids','chapter_id')]:
        valid={n['id'] for c in catalogs if matching(c,q,kind) for n in c['nodes']}
        ids=raw.get(field,[]) or ([scope[selected]] if scope.get(selected) else [])
        if isinstance(ids,list):q[field]=list(dict.fromkeys(str(x) for x in ids if str(x) in valid))
    q.setdefault('created_at',stamp());return q

def stamp(): return time.strftime('%Y-%m-%d %H:%M:%S')
def fingerprint(q): return content.digest(json.dumps([q.get(k,'') for k in ('content','answer','analysis','notes')],ensure_ascii=False).encode())
def decorate(q):
    q=copy.deepcopy(q)
    for key,value in {'knowledge_tree_ids':[],'chapter_ids':[],'tags':[],'status':'draft','notes':'','archived':False,'edition_id':None,'grade_id':None,'created_at':'','updated_at':''}.items(): q.setdefault(key,value)
    q['content_sha256']=fingerprint(q)
    # A hash of classification metadata prevents a second client silently replacing it.
    q['classification_sha256']=content.digest(json.dumps([q.get(k) for k in ('knowledge_tree_ids','chapter_ids','tags','edition_id')],ensure_ascii=False).encode())
    return q
def identity(v):
    if isinstance(v,bool) or not re.fullmatch(r'[1-9]\d{0,12}',str(v)): raise ValueError('目录编号须为正整数。')
    return int(v)
def strings(v,max_count=100):
    if not isinstance(v,list) or len(v)>max_count or any(not isinstance(x,str) or len(x)>120 for x in v): raise ValueError('分类或标签列表无效。')
    return list(dict.fromkeys(x.strip() for x in v if x.strip()))
def catalog(raw):
    kind=raw.get('kind')
    if kind not in ('knowledge','chapter'): raise ValueError('目录类型须为知识点或教材章节。')
    c={'kind':kind,'subject_id':identity(raw.get('subject_id')),'phase_id':identity(raw.get('phase_id')),'nodes':[]}
    if kind=='chapter': c['edition_id']=identity(raw.get('edition_id'))
    c['label']=str(raw.get('label') or ('知识点' if kind=='knowledge' else '教材章节'))[:120]
    c['id']='-'.join(str(c[k]) for k in ('kind','subject_id','phase_id')+ (('edition_id',) if kind=='chapter' else ()))
    nodes=raw.get('nodes')
    if not isinstance(nodes,list) or not 1<=len(nodes)<=10000: raise ValueError('目录须含 1–10000 个节点。')
    seen={}
    for n in nodes:
        if not isinstance(n,dict): raise ValueError('目录节点格式错误。')
        ident=str(identity(n.get('id'))); parent=str(identity(n['parent_id'])) if n.get('parent_id') else None
        name=n.get('name')
        if ident in seen or not isinstance(name,str) or not name.strip() or len(name)>180: raise ValueError('节点重号或名称无效。')
        seen[ident]={'id':ident,'parent_id':parent,'name':name.strip()}
    for ident,n in seen.items():
        trail={ident}; parent=n['parent_id']
        while parent:
            if parent not in seen or parent in trail: raise ValueError('目录缺少父节点或存在循环。')
            trail.add(parent); parent=seen[parent]['parent_id']
            if len(trail)>60: raise ValueError('目录层级过深。')
    c['nodes']=list(seen.values());c['saved_at']=stamp();return c
def matching(c,q,kind):
    return c['kind']==kind and c['subject_id']==q.get('subject_id') and c['phase_id']==q.get('phase_id') and (kind!='chapter' or c.get('edition_id')==q.get('edition_id'))
def validate_links(q,catalogs):
    q['tags']=strings(q.get('tags',[]))
    for kind,field in [('knowledge','knowledge_tree_ids'),('chapter','chapter_ids')]:
        q[field]=strings(q.get(field,[]))
        allowed={n['id'] for c in catalogs if matching(c,q,kind) for n in c['nodes']}
        if any(x not in allowed for x in q[field]): raise ValueError('知识点或章节不属于题目当前学科、学段、教材；请先加载正确目录。')
    return q
def verify_assets(root,q):
    for a in q.get('assets',[]):
        p=content.asset_path(root,a['path'])
        if not p.is_file() or content.digest(p.read_bytes())!=a.get('sha256'): raise ValueError('配图缺失或已被修改，请重载后再核对。')
    if q.get('prepare_error'): raise ValueError('题目附件尚未完整保存。')
def audit(root,q):
    d=root/'history';d.mkdir(exist_ok=True)
    (d/(uuid.uuid4().hex+'.json')).write_text(json.dumps(q,ensure_ascii=False),encoding='utf-8')
def select(b,questions):
    ids=strings(b.get('ids',[]),200)
    if not ids or any(i not in questions for i in ids): raise ValueError('请选择当前题库内的题目。')
    return [decorate(questions[i]) for i in ids]
def guarded(b,q):
    if b.get('hashes',{}).get(q['id'])!=fingerprint(q): raise ValueError('题目已变化，请重新读取后操作。')
def descendants(c,node):
    result={str(node)}
    while True:
        more={n['id'] for n in c['nodes'] if n['parent_id'] in result}
        if more<=result:return result
        result|=more
def stats(state):
    rows=[q for q in state['questions'] if not q.get('archived')]
    used={i for ex in state['exports'] for i in ex.get('question_ids',[])}
    return {'total':len(rows),'draft':sum(q['status']!='reviewed' for q in rows),'unclassified':sum(not q['knowledge_tree_ids'] for q in rows),'papers':len(state['exports']),'unused':sum(q['id'] not in used for q in rows)}

def search(state,args):
    rows=[];used={i for e in state['exports'] for i in e.get('question_ids',[])}
    selected=next((c for c in state['catalogs'] if c['id']==args.catalog),None) if args.catalog else None
    if args.catalog and not selected:raise ValueError('目录不存在。')
    if args.node and not selected:raise ValueError('按节点筛选须同时提供 --catalog。')
    nodes=descendants(selected,args.node) if args.node else None
    for q in state['questions']:
        if q['archived']!=args.archived:continue
        if args.status and (not q['knowledge_tree_ids'] if args.status=='unclassified' else q['status']==args.status) is False:continue
        if args.tag and not any(t==args.tag or t.startswith(args.tag+'/') for t in q['tags']):continue
        if args.type and q['type']!=args.type:continue
        if args.unused and q['id'] in used:continue
        if selected and not matching(selected,q,selected['kind']):continue
        if nodes and not nodes.intersection(q['knowledge_tree_ids' if selected['kind']=='knowledge' else 'chapter_ids']):continue
        text=dom.fragment_fromstring(q['content'] or '<span></span>',create_parent='div').text_content()
        if args.keyword.casefold() not in (text+' '+str(q.get('title',''))+' '+str(q.get('knowledge',''))+' '+' '.join(q['tags'])).casefold():continue
        rows.append({k:q.get(k) for k in ('id','title','type','status','subject_id','phase_id','knowledge_tree_ids','chapter_ids','tags','content_sha256')}|{'text':text[:220]})
    return {'revision':state['revision'],'items':rows[:max(1,min(args.limit,200))],'count':len(rows)}
def filedata(b,limit=250*1024*1024):
    try: data=base64.b64decode(b.get('file_base64',''),validate=True)
    except Exception: raise ValueError('上传文件编码错误。') from None
    if not data or len(data)>limit:raise ValueError(f'文件为空或超过 {limit//1024//1024} MB。')
    return data
def snapshot(w,s,questions,kind='backup',ids=None,include_solutions=True):
    rows=[decorate(q) for q in questions.values() if ids is None or q['id'] in ids]
    state=copy.deepcopy(s)
    if kind=='package':state={k:state.get(k,[]) for k in ('catalogs',)}
    files={}
    for q in rows:
        if not include_solutions:
            q['answer']=q['analysis']=q['notes']='';q.pop('editable',None);q.pop('original_payload',None);q.pop('source_pdf',None)
            q['assets']=[a for a in q.get('assets',[]) if a['path'] in q['content']]
            q['mcp']={'solutions_status':'not_returned','auth_mode':'api_key','tool':'package'}
        if kind!='backup':verify_assets(w.root,q)
        for a in q.get('assets',[]):
            p=content.asset_path(w.root,a['path'])
            if p.is_file():files[a['path']]=p.read_bytes()
    if kind=='backup':
        for folder in ['raw','pdf','exports','history']:
            for p in (w.root/folder).rglob('*') if (w.root/folder).exists() else []:
                if p.is_file(): files[p.relative_to(w.root).as_posix()]=p.read_bytes()
    if sum(len(v) for v in files.values())>250*1024*1024: raise ValueError('备份大于 250 MB，请先分批导出题目包。')
    manifest={'schema':'tizhuang.studio-package/v1','kind':kind,'includes_solutions':include_solutions,'state':state,'questions':rows,'hashes':{k:content.digest(v) for k,v in files.items()}}
    ident=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    folder=w.root/'backups';folder.mkdir(exist_ok=True);path=folder/(ident+'.zip')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
        for name,data in files.items():z.writestr(name,data)
    return {'id':ident,'kind':kind,'count':len(rows),'created_at':stamp(),'url':'/backups/'+ident+'.zip'}
def unpack_archive(data):
    files={}
    with zipfile.ZipFile(BytesIO(data)) as z:
        infos=z.infolist()
        if len(infos)>12000 or sum(i.file_size for i in infos)>250*1024*1024:raise ValueError('压缩包解压规模过大。')
        for i in infos:
            name=i.filename
            if name in files or i.is_dir() or '\\' in name or ':' in name or name.startswith('/') or '..' in name.split('/') or ((i.external_attr>>16)&0o170000)==0o120000:raise ValueError('压缩包路径或条目不安全。')
            if not re.fullmatch(r'(?:manifest.json|questions.json|Assets/[a-f0-9]{64}\.(?:png|jpg|jpeg|gif|webp)|(?:raw|pdf|exports|history)/[a-zA-Z0-9_./-]+)',name):raise ValueError('压缩包含不支持的文件。')
            files[name]=z.read(i)
    name='manifest.json' if 'manifest.json' in files else 'questions.json'
    if name not in files:raise ValueError('缺少题目包清单。')
    manifest=json.loads(files.pop(name).decode('utf-8-sig'))
    if manifest.get('schema')=='tizhuang.studio-package/v1' and set(files)!=set(manifest.get('hashes',{})):raise ValueError('备份包含未校验文件。')
    for k,v in manifest.get('hashes',{}).items():
        if k not in files or content.digest(files[k])!=v:raise ValueError('备份文件校验失败。')
    return manifest,files
def install_files(root,files):
    for name,data in files.items():
        p=(root/name).resolve()
        if root.resolve() not in p.parents:raise ValueError('文件路径越界。')
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)

def apply(w,b,s,questions):
    """Return pending question rows + report; caller commits rows and state atomically."""
    from engine import prepare
    action=b['action'];pending=[];report={};s.setdefault('catalogs',[]);s.setdefault('pdf_batches',[])
    if action in ('catalog-save','catalog-fetch'):
        raw=copy.deepcopy(b)
        if action=='catalog-fetch':
            raw['nodes']=w.service.meta('knowledge-points' if b.get('kind')=='knowledge' else 'chapters',{k:b[k] for k in ['subject_id','phase_id','edition_id'] if b.get(k)}|{'limit':5000})
        c=catalog(raw);prev=next((x for x in s['catalogs'] if x['id']==c['id']),None)
        if prev and prev['nodes']!=c['nodes'] and b.get('replace') is not True:raise ValueError('已有本地目录；若要更新，请明确选择替换目录。')
        new=[x for x in s['catalogs'] if x['id']!=c['id']]+[c]
        for q in questions.values():
            if matching(c,q,c['kind']):validate_links(decorate(q),new)
        s['catalogs']=new;report={'catalog_id':c['id'],'nodes':len(c['nodes'])}
    elif action=='classify':
        for q in select(b,questions):
            guarded(b,q)
            for key in ['knowledge_tree_ids','chapter_ids','tags','edition_id']:
                if key in b:q[key]=b[key]
            if q.get('edition_id') is not None:q['edition_id']=identity(q['edition_id'])
            validate_links(q,s['catalogs']);audit(w.root,questions[q['id']]);q['updated_at']=stamp();pending.append(q)
    elif action=='auto-classify':
        rows=select(b,questions) if b.get('ids') else [decorate(q) for q in questions.values() if not q.get('archived')]
        for q in rows:
            if q['knowledge_tree_ids']:continue
            labels={x.strip() for x in re.split(r'[,，;；、·\n]',q.get('knowledge','')) if x.strip()}|set(q['tags'])
            names={}
            for c in s['catalogs']:
                if matching(c,q,'knowledge'):
                    for n in c['nodes']:names.setdefault(n['name'],[]).append(n['id'])
            ids=[v[0] for k,v in names.items() if k in labels and len(v)==1]
            if ids:
                audit(w.root,questions[q['id']]);q['knowledge_tree_ids']=list(dict.fromkeys(ids));q['updated_at']=stamp();pending.append(q)
        report={'classified_ids':[q['id'] for q in pending],'remaining_ids':[q['id'] for q in rows if not q['knowledge_tree_ids']]}
    elif action in ('review','archive'):
        if b.get('confirm') is not True:raise ValueError('请明确确认本次操作。')
        if action=='review' and b.get('actor')=='Agent' and b.get('teacher_confirmed') is not True:raise ValueError('请由老师本人核对，Agent 不能自行确认。')
        for q in select(b,questions):
            guarded(b,q)
            if action=='review':
                verify_assets(w.root,q);q['status']='reviewed';q['reviewed_at']=stamp()
            else:
                q['archived']=bool(b.get('archived',True))
                if q['archived'] and any(i['id']==q['id'] for i in s['items']):raise ValueError('请先将题目移出组卷篮再归档。')
            audit(w.root,questions[q['id']]);q['updated_at']=stamp();pending.append(q)
    elif action in ('edit','create'):
        if action=='edit':
            q=decorate(questions.get(b.get('id'),{}))
            if 'id' not in q:raise ValueError('题目不存在。')
            guarded(b,q)
        else:q=decorate({'id':'local-'+uuid.uuid4().hex,'subject_id':identity(b.get('subject_id')),'phase_id':identity(b.get('phase_id')),'source':{'label':'自编题目'},'assets':[],'created_at':stamp()})
        text=b.get('text');fmt=b.get('format','markdown')
        if not isinstance(text,dict) or fmt not in ('markdown','html') or not isinstance(text.get('content'),str) or not text['content'].strip():raise ValueError('请填写可编辑题干。')
        for key in ['content','answer','analysis']:
            v=text.get(key,'')
            if not isinstance(v,str) or len(v)>500000:raise ValueError('题目文本无效或过长。')
            if re.search(r'!\[[^\]]*\]\(\s*(?:https?:|//)|<img[^>]+src=[\"\x27](?:https?:|//)',v,re.I):raise ValueError('编辑题目只允许已保存的本地配图，请使用 Assets 路径。')
            q[key]=content.render(v,fmt)
        q['editable']={**text,'format':fmt}
        if q.get('mcp',{}).get('solutions_status')=='not_returned' and (text.get('answer','').strip() or text.get('analysis','').strip()):q['mcp']['solutions_status']='provided_locally'
        q['type']=str(b.get('type',q.get('type','解答题')))[:40];q['notes']=str(b.get('notes',q['notes']))[:20000]
        q['title']=str(b.get('title',q.get('title','')))[:120];q['status']='draft';q['updated_at']=stamp()
        q=prepare(q,w.root)
        if action=='edit':audit(w.root,questions[q['id']])
        pending=[q];report={'id':q['id']}
    elif action in ('backup','package-export'):
        ids=b.get('ids') if action=='package-export' else None
        if action=='package-export':select(b,questions)
        report=snapshot(w,s,questions,'backup' if action=='backup' else 'package',ids,b.get('include_solutions',True))
    elif action in ('restore','package-import'):
        if action=='restore' and b.get('confirm') is not True:raise ValueError('恢复会替换当前题库状态，请确认；恢复前会先备份。')
        data=filedata(b);m,files=unpack_archive(data)
        if m.get('schema') not in ('tizhuang.studio-package/v1','tizhuang.question-package/v1'):raise ValueError('不支持的题目包格式。')
        restore=action=='restore'
        if restore and m.get('kind')!='backup':raise ValueError('请选择完整工作台备份。')
        cats=[catalog(c) for c in m.get('state',{}).get('catalogs',[])]
        if not restore:
            existing_ids={c['id'] for c in s['catalogs']}
            for c in cats:
                old=next((x for x in s['catalogs'] if x['id']==c['id']),None)
                if old and old['nodes']!=c['nodes']:raise ValueError('题目包目录与本地同范围目录不同，请先核对并更新目录后再导入。')
            cats=s['catalogs']+[c for c in cats if c['id'] not in existing_ids]
        rawrows=m.get('questions')
        if not isinstance(rawrows,list) or len(rawrows)>10000:raise ValueError('题目包清单无效。')
        ids=set()
        for raw in rawrows:
            ident=str(raw.get('id',''))
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',ident) or ident in ids:raise ValueError('题号无效或重复。')
            ids.add(ident)
            if not restore and ident in questions:continue
            q=decorate(raw);q['id']=ident;q['subject_id']=identity(q.get('subject_id'));q['phase_id']=identity(q.get('phase_id'))
            # Standalone local-bank packages may lack taxonomy snapshots; leave their IDs pending until a tree is supplied.
            if m['schema']=='tizhuang.question-package/v1':
                q['unmapped_knowledge_ids']=q['knowledge_tree_ids'];q['unmapped_chapter_ids']=q['chapter_ids'];q['knowledge_tree_ids']=[];q['chapter_ids']=[]
            if m.get('includes_solutions') is False:q['mcp']={'solutions_status':'not_returned','auth_mode':'api_key','tool':'package'}
            validate_links(q,cats)
            for a in q.get('assets',[]):
                content.asset_path(w.root,a['path'])
                if a['path'] not in files or content.digest(files[a['path']])!=a['sha256']:
                    if restore:q['prepare_error']='备份中的原题附件不完整，请修复配图后重新核对。';q['status']='draft'
                    else:raise ValueError('题目包缺少图片或图片校验失败。')
            for key in ['content','answer','analysis']:
                q[key]=content.render(q.get(key,''),q.get('content_format','html'))
                for src in dom.fragment_fromstring(q[key] or '<span></span>',create_parent='div').xpath('.//img/@src'):
                    if src not in {a['path'] for a in q.get('assets',[])}:raise ValueError('正文引用了未在清单登记的图片。')
            q['content_format']='html'
            if not restore:q['status']='draft'
            pending.append(q)
        if restore:
            restored=m.get('state',{})
            from engine import number
            if not isinstance(restored.get('items'),list) or len(restored['items'])>200 or any(i.get('id') not in ids for i in restored['items']):raise ValueError('备份组卷篮引用无效。')
            if len({i['id'] for i in restored['items']})!=len(restored['items']):raise ValueError('备份组卷篮题目重复。')
            for i in restored['items']:i['score']=number(i.get('score'),0,1000)
            for key,lo,hi in [('duration_minutes',1,600),('answer_space_mm',0,100)]:restored[key]=number(restored.get(key),lo,hi,True)
            if not isinstance(restored.get('title'),str) or not 1<=len(restored['title'])<=120:raise ValueError('备份试卷标题无效。')
            for e in restored.get('exports',[]):
                if not re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{8}',e.get('id','')):raise ValueError('备份试卷编号无效。')
                e['count']=number(e.get('count'),0,200,True);e['revision']=number(e.get('revision'),0,100000000,True)
                for k in ['student','teacher','student_html','teacher_html']:
                    if k in e and e[k]!='/exports/'+e['id']+'/'+k.replace('_html','')+('.html' if k.endswith('_html') else '.docx'):raise ValueError('备份下载路径无效。')
            for batch in restored.get('pdf_batches',[]):
                if not re.fullmatch(r'[a-f0-9]{24}',batch.get('id','')):raise ValueError('备份 PDF 批次号无效。')
                batch['subject_id']=identity(batch.get('subject_id'));batch['phase_id']=identity(batch.get('phase_id'))
                if not isinstance(batch.get('filename'),str) or len(batch['filename'])>120:raise ValueError('备份 PDF 文件名无效。')
                if not isinstance(batch.get('pages'),list) or not 1<=len(batch['pages'])<=60:raise ValueError('备份 PDF 页数无效。')
                batch['question_ids']=strings(batch.get('question_ids',[]),10000)
                for n,p in enumerate(batch['pages'],1):
                    if p.get('number')!=n or p.get('image')!=f'page-{n}.png':raise ValueError('备份 PDF 页面路径无效。')
                    if not isinstance(p.get('text'),str) or len(p['text'])>1000000:raise ValueError('备份 PDF 页面文字无效。')
                    for key in ['width','height']:p[key]=number(p.get(key),1,20000)
            old=snapshot(w,s,questions)
            cursors=restored.get('fetch_cursors',{})
            if not isinstance(cursors,dict) or len(cursors)>10000:raise ValueError('备份取题进度无效。')
            for key,value in cursors.items():
                fields=json.loads(key)
                if not isinstance(fields,list) or len(fields)!=7 or any(not isinstance(v,str) or len(v)>100 for v in fields):raise ValueError('备份取题范围无效。')
                number(value,0,10020,True)
            s['fetch_cursors']=cursors
            for key in ('title','duration_minutes','answer_space_mm','items','exports','pdf_batches'):s[key]=restored.get(key,s.get(key,[]))
            report={'before_restore_backup':old,'replace_all_questions':True}
        if not restore:
            needed={a['path'] for q in pending for a in q.get('assets',[])}
            files={k:v for k,v in files.items() if k in needed}
            for name,data in files.items():
                p=content.asset_path(w.root,name)
                if p.exists() and p.read_bytes()!=data:raise ValueError('本地同名附件内容不同，导入已停止。')
        s['catalogs']=cats;install_files(w.root,files);report['imported_ids']=[q['id'] for q in pending]
    elif action in ('pdf-prepare','pdf-import'):
        import studio_pdf
        return studio_pdf.apply(w,b,s,questions)
    else:raise ValueError('未知题库操作。')
    return pending,report

def print_html(root,manifest,teacher):
    from paper_html import render
    return render(root,manifest,teacher)
