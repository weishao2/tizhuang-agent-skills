"""Run a private loopback workspace, or operate its shared basket from an Agent."""
import argparse, base64, hashlib, hmac, json, mimetypes, os, re, secrets, sys, time, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse,parse_qs
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

def emit(value):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False))

def serve(root,port):
    from engine import Workspace,ROOT,StudioError
    Path(root).mkdir(parents=True,exist_ok=True)
    # A workspace has a single writer service. Agents always call that service.
    lease=open(Path(root)/'service.lock','a+b')
    lease.seek(0); lease.write(b'0'); lease.flush(); lease.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        lease.close(); raise ValueError('这个工作目录已有工作台在运行，请复用 session.json 中的地址。') from None
    workspace=Workspace(root)
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,value,status=200,mime='application/json; charset=utf-8',cookie=False,filename=None):
            data=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode() if mime.startswith('application/json') else value
            self.send_response(status)
            self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if cookie: self.send_header('Set-Cookie',f'studio_session={token}; HttpOnly; SameSite=Strict; Path=/')
            if filename: self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.end_headers(); self.wfile.write(data)
        def check(self,auth=True):
            host=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host')!=host: raise StudioError('仅允许从本机工作台访问。',403)
            if self.headers.get('Origin') not in (None,'http://'+host): raise StudioError('请求来源不受信任。',403)
            if self.headers.get('Sec-Fetch-Site') not in (None,'none','same-origin'): raise StudioError('请直接打开本机工作台。',403)
            if auth:
                cookie=SimpleCookie(); cookie.load(self.headers.get('Cookie',''))
                provided=self.headers.get('X-Studio-Token','') or (cookie['studio_session'].value if 'studio_session' in cookie else '')
                if not hmac.compare_digest(provided,token): raise StudioError('工作台会话已过期，请重新打开首页。',401)
        def do_GET(self):
            try:
                parsed=urlparse(self.path); path=parsed.path
                self.check(path!='/')
                if path=='/': return self.send((ROOT/'assets/web/index.html').read_bytes(),mime='text/html; charset=utf-8',cookie=True)
                if path=='/api/state':
                    state=workspace.state()
                    if parse_qs(parsed.query).get('view')==['web']:
                        from content import stem_layout
                        for question in state['questions']:
                            display=stem_layout(workspace.root,question)
                            if display!=question.get('content',''):question['display_content']=display
                    return self.send(state)
                if path=='/api/backups':
                    return self.send([{'id':p.stem,'size':p.stat().st_size,'url':'/backups/'+p.name} for p in sorted((workspace.root/'backups').glob('*.zip'),reverse=True) if re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{8}',p.stem)])
                if path=='/api/quota': return self.send(workspace.service.quota())
                if path=='/api/directory-quota': return self.send(workspace.service.get('/v1/local-bank/directory-quota',protected=True))
                if path.startswith('/api/meta/'):
                    name=path.split('/')[-1]; params={k:v[-1] for k,v in parse_qs(parsed.query).items()}
                    if any(k not in ['subject_id','phase_id','edition_id','grade_id','limit'] for k in params): raise StudioError('不支持的目录参数。')
                    return self.send(workspace.service.meta(name,params))
                if re.fullmatch(r'/web/[a-z.-]+',path):
                    p=ROOT/'assets'/path.lstrip('/')
                elif re.fullmatch(r'/Assets/[a-f0-9]{64}\.(png|jpg|jpeg|webp|gif)',path): p=workspace.root/path.lstrip('/')
                elif re.fullmatch(r'/exports/[0-9-]+[a-f0-9]{8}/(student|teacher)\.(docx|html)',path):
                    parts=path.split('/')
                    if not any(e['id']==parts[2] for e in workspace.state()['exports']): raise StudioError('试卷未完整生成。',404)
                    p=workspace.root/path.lstrip('/')
                    if p.suffix=='.html':
                        import papers, library
                        # Display the latest layout without overwriting any saved artifact.
                        snapshot_file=p.parent/'snapshot.json'
                        if snapshot_file.is_file():
                            preview=library.print_html(workspace.root,papers.snapshot(workspace.root,parts[2]),parts[3]=='teacher.html')
                            return self.send(preview.encode('utf-8'),mime='text/html; charset=utf-8')
                elif re.fullmatch(r'/backups/\d{8}-\d{6}-[a-f0-9]{8}\.zip',path):p=workspace.root/path.lstrip('/')
                elif re.fullmatch(r'/pdf/[a-f0-9]{24}/(?:page-\d+\.(?:png|txt)|original.pdf|manifest.json)',path):
                    if not any(x['id']==path.split('/')[2] for x in workspace.state()['pdf_batches']):raise StudioError('批次不存在。',404)
                    p=workspace.root/path.lstrip('/')
                else: raise StudioError('页面不存在。',404)
                if not p.is_file(): raise StudioError('文件不存在。',404)
                self.send(p.read_bytes(),mime=mimetypes.guess_type(p)[0] or 'application/octet-stream',filename=p.name if p.suffix in ('.docx','.zip','.pdf') else None)
            except StudioError as e: self.send({'ok':False,'error':str(e)},e.status)
            except Exception: self.send({'ok':False,'error':'读取失败，请检查本机工作台。'},500)
        def do_POST(self):
            try:
                self.check()
                if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise StudioError('请求须为 JSON。',415)
                size=int(self.headers.get('Content-Length',0))
                limit=350*1024*1024 if self.path=='/api/library' else 2*1024*1024 if self.path=='/api/import-mcp' else 65536
                if not 0<size<=limit: raise StudioError('请求大小不受支持。',413)
                b=json.loads(self.rfile.read(size))
                if not isinstance(b,dict): raise StudioError('请求内容无效。')
                if self.path in ('/api/command','/api/library'): return self.send(workspace.operation(b))
                if self.path=='/api/import-mcp':
                    return self.send(workspace.operation({**b,'action':'import-mcp','actor':'Agent'}))
                if self.path=='/api/connect':
                    key=str(b.get('key','')).strip()
                    if key and (len(key)>250 or not re.fullmatch(r'[A-Za-z0-9_-]+',key)): raise StudioError('Key 格式无效。')
                    # Session memory only, never in SQLite, logs, packages or command history.
                    with workspace.lock: workspace.service.key=key
                    return self.send({'ok':True,'connected':bool(key)})
                raise StudioError('操作不存在。',404)
            except StudioError as e: self.send({'ok':False,'error':str(e)},e.status)
            except Exception: self.send({'ok':False,'error':'处理失败，请检查输入或工作台环境。'},500)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    session=workspace.root/'session.json'
    session.write_text(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','token':token,'pid':os.getpid()}),encoding='utf-8')
    try: os.chmod(session,0o600)
    except OSError: pass
    emit({'ok':True,'url':f'http://127.0.0.1:{server.server_port}','workspace':str(workspace.root)})
    sys.stdout.flush()
    try: server.serve_forever()
    finally:
        server.server_close()
        if session.exists() and json.loads(session.read_text(encoding='utf-8')).get('token')==token: session.unlink()
        lease.close()

def remote(root,method,path,body=None):
    session=json.loads((Path(root)/'session.json').read_text(encoding='utf-8'))
    if not re.fullmatch(r'http://127\.0\.0\.1:\d+',session['url']): raise ValueError('工作台地址无效。')
    req=Request(session['url']+path,method=method,headers={'X-Studio-Token':session['token'],'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(req,timeout=180) as r: return json.load(r)
    except HTTPError as e:
        try: message=json.load(e).get('error','操作失败')
        except Exception: message='操作失败'
        raise ValueError(message) from None

def main():
    p=argparse.ArgumentParser(description='题庄 2.0：Agent 与页面共用组卷篮')
    p.add_argument('--workspace',required=True,type=Path)
    sub=p.add_subparsers(dest='command',required=True)
    run=sub.add_parser('serve'); run.add_argument('--port',type=int,default=4186)
    sub.add_parser('doctor'); sub.add_parser('state'); sub.add_parser('quota')
    meta=sub.add_parser('meta'); meta.add_argument('name'); meta.add_argument('--params',default='{}')
    search=sub.add_parser('search'); search.add_argument('--keyword',default=''); search.add_argument('--limit',type=int,default=20)
    search.add_argument('--catalog');search.add_argument('--node');search.add_argument('--tag');search.add_argument('--type')
    search.add_argument('--status',choices=['draft','reviewed','unclassified']);search.add_argument('--unused',action='store_true');search.add_argument('--archived',action='store_true')
    show=sub.add_parser('show'); show.add_argument('--ids',nargs='+',required=True)
    cmd=sub.add_parser('command'); cmd.add_argument('--json',required=True,help='JSON 字符串或 @文件路径；必须带 revision/action/request_id。')
    lib=sub.add_parser('library',help='目录、分类、编辑、PDF、备份；通过同一服务写入。');lib.add_argument('--json',required=True)
    lib.add_argument('--file',type=Path,help='pdf-prepare 或 restore/package-import 的本地文件；仅由 CLI 读取。')
    batch=sub.add_parser('pdf-batch');batch.add_argument('--id',required=True)
    imp=sub.add_parser('import-mcp',help='保存 Agent MCP 取题结果；不接收 Key 或 OAuth 令牌。')
    imp.add_argument('--file',type=Path,required=True)
    imp.add_argument('--auth',choices=['oauth','api_key'],required=True)
    imp.add_argument('--tool',choices=['search_questions','get_question'],required=True)
    imp.add_argument('--subject-id',type=int,required=True); imp.add_argument('--phase-id',type=int,required=True)
    imp.add_argument('--revision',type=int,required=True); imp.add_argument('--request-id',required=True)
    imp.add_argument('--add-to-basket',action='store_true')
    args=p.parse_args()
    if args.command=='doctor':
        import importlib.util
        missing=[m for m in ['docx','lxml','PIL','markdown','mathml2omml','latex2mathml','pypdfium2'] if importlib.util.find_spec(m) is None]
        emit({'ok':not missing,'python':sys.executable,'missing':missing,'hint':'使用当前 Python 安装 scripts/requirements.txt' if missing else '环境正常，可启动工作台'}); return 1 if missing else 0
    if args.command=='serve': serve(args.workspace,args.port); return 0
    if args.command=='import-mcp':
        from mcp_import import MAX_BYTES
        with args.file.open('rb') as f: raw=f.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('MCP 结果超过 2 MB，请按批保存。')
        result=remote(args.workspace,'POST','/api/import-mcp',{'result':json.loads(raw.decode('utf-8-sig')),
            'auth_mode':args.auth,'tool':args.tool,'subject_id':args.subject_id,'phase_id':args.phase_id,
            'revision':args.revision,'request_id':args.request_id,'add_to_basket':args.add_to_basket})
    elif args.command in ('command','library'):
        raw=Path(args.json[1:]).read_text(encoding='utf-8-sig') if args.json.startswith('@') else args.json
        b=json.loads(raw); b['actor']='Agent'
        if args.command=='library' and args.file:
            limit=30*1024*1024 if b.get('action')=='pdf-prepare' else 250*1024*1024
            if args.file.stat().st_size>limit:raise ValueError('文件过大，请分批导入。')
            b['file_base64']=base64.b64encode(args.file.read_bytes()).decode();b['filename']=args.file.name
        result=remote(args.workspace,'POST','/api/library' if args.command=='library' else '/api/command',b)
    elif args.command=='quota': result=remote(args.workspace,'GET','/api/quota')
    elif args.command=='meta':
        from urllib.parse import urlencode
        result=remote(args.workspace,'GET','/api/meta/'+args.name+'?'+urlencode(json.loads(args.params)))
    else:
        result=remote(args.workspace,'GET','/api/state')
        if args.command=='search':
            import library
            result=library.search(result,args)
        elif args.command=='show': result={'revision':result['revision'],'questions':[q for q in result['questions'] if q['id'] in args.ids]}
        elif args.command=='pdf-batch':
            match=next((x for x in result['pdf_batches'] if x['id']==args.id),None)
            if not match:raise ValueError('批次不存在。')
            result={'revision':result['revision'],'batch':match,'folder':str(args.workspace.resolve()/'pdf'/args.id)}
        else: result={k:v for k,v in result.items() if k!='questions'}|{'question_count':len(result['questions'])}
    emit(result); return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (Exception,) as e:
        # Do not leak tracebacks or request headers / secrets.
        message=str(e) if isinstance(e,(ValueError,FileNotFoundError)) else '工作台不可用，请先运行 doctor，再启动 serve。'
        emit({'ok':False,'error':message,'hint':'确认 --workspace 与已打开页面使用同一个目录；不自动重试取题。'}); sys.exit(1)
