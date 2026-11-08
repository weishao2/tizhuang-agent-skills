import json,os,subprocess,sys,tempfile,time,unittest,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/studio.py'

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(); cls.root=Path(cls.temp.name)
        cls.proc=subprocess.Popen([sys.executable,str(SCRIPT),'--workspace',str(cls.root),'serve','--port','0'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try: cls.session=json.loads((cls.root/'session.json').read_text()); break
            except (FileNotFoundError,json.JSONDecodeError): time.sleep(.05)
        else: raise RuntimeError('预览服务未启动')
    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.wait(timeout=10); cls.temp.cleanup()
    def request(self,path,headers=None,body=None):
        h={'X-Studio-Token':self.session['token'],**(headers or {})}
        if body is not None: h['Content-Type']='application/json'
        req=Request(self.session['url']+path,headers=h,data=json.dumps(body).encode() if body is not None else None)
        return urlopen(req,timeout=10)
    def test_unauthenticated_state_rejected(self):
        with self.assertRaises(HTTPError) as e: self.request('/api/state',{'X-Studio-Token':''})
        self.assertEqual(e.exception.code,401)
    def test_host_and_origin_rejected(self):
        for headers in [{'Host':'evil.example'},{'Origin':'https://evil.example'},{'Sec-Fetch-Site':'cross-site'}]:
            with self.assertRaises(HTTPError) as e: self.request('/api/state',headers)
            self.assertEqual(e.exception.code,403)
    def test_same_workspace_cli_and_http(self):
        with self.request('/api/state') as r: state=json.load(r)
        cmd={'action':'settings','title':'共享状态验收','revision':state['revision'],'request_id':uuid.uuid4().hex}
        command_path=self.root/'command.json'; command_path.write_text(json.dumps(cmd),encoding='utf-8')
        p=subprocess.run([sys.executable,str(SCRIPT),'--workspace',str(self.root),'command','--json','@'+str(command_path)],capture_output=True)
        self.assertEqual(p.returncode,0,p.stdout)
        with self.request('/api/state') as r: updated=json.load(r)
        self.assertEqual(updated['title'],'共享状态验收'); self.assertEqual(updated['updated_by'],'Agent')
    def test_key_not_in_state_or_database(self):
        value='test-only-do-not-use-key'
        with self.request('/api/connect',body={'key':value}) as r: self.assertTrue(json.load(r)['connected'])
        with self.request('/api/state') as r: self.assertNotIn(value,r.read().decode())
        self.assertNotIn(value.encode(),(self.root/'studio.sqlite3').read_bytes())
        with self.assertRaises(HTTPError) as e: self.request('/session.json')
        self.assertEqual(e.exception.code,404)
    def test_single_server_lease_preserves_session(self):
        before=(self.root/'session.json').read_bytes()
        p=subprocess.run([sys.executable,str(SCRIPT),'--workspace',str(self.root),'serve','--port','0'],capture_output=True,timeout=10)
        self.assertEqual(p.returncode,1); self.assertEqual(before,(self.root/'session.json').read_bytes())
    def test_unknown_download_is_not_served(self):
        with self.assertRaises(HTTPError) as e: self.request('/exports/20261025-111111-12345678/student.docx')
        self.assertEqual(e.exception.code,404)

    def test_mcp_cli_import_shared_http_state_large_payload(self):
        with self.request('/api/state') as r: state=json.load(r)
        payload={'structuredContent':{'data':{'items':[{'id':7891,'subject_id':2,
                 'title_html':'MCP 接续测试 '+('数学题干 '*15000),'answer_html':'答案','question_type':'解答题'}]}},'isError':False}
        path=self.root/'mcp-result.json'; path.write_text(json.dumps(payload),encoding='utf-8')
        command=[sys.executable,str(SCRIPT),'--workspace',str(self.root),'import-mcp','--file',str(path),
                 '--auth','oauth','--tool','search_questions','--subject-id','2','--phase-id','2',
                 '--revision',str(state['revision']),'--request-id',uuid.uuid4().hex,'--add-to-basket']
        p=subprocess.run(command,capture_output=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stdout)
        with self.request('/api/state') as r: state=json.load(r)
        self.assertTrue(any(i['id']=='7891' for i in state['items']))
        self.assertEqual(state['updated_by'],'Agent')
        p=subprocess.run(command,capture_output=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stdout)
        with self.request('/api/state') as r: latest=json.load(r)
        self.assertEqual(latest['revision'],state['revision'])

    def test_mcp_endpoint_auth_and_origin(self):
        for headers,status in [({'X-Studio-Token':''},401),({'Origin':'https://evil.example'},403)]:
            with self.assertRaises(HTTPError) as e: self.request('/api/import-mcp',headers,body={})
            self.assertEqual(e.exception.code,status)

    def test_library_cli_and_browser_share_question_edit_state(self):
        with self.request('/api/state') as r:s=json.load(r)
        command={'action':'create','subject_id':2,'phase_id':2,'text':{'content':'CLI shared $x=2$','answer':'2'},'revision':s['revision'],'request_id':uuid.uuid4().hex}
        file=self.root/'library-operation.json';file.write_text(json.dumps(command),encoding='utf-8')
        result=subprocess.run([sys.executable,str(SCRIPT),'--workspace',str(self.root),'library','--json','@'+str(file)],capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout)
        id=json.loads(result.stdout)['id']
        with self.request('/api/state') as r:s=json.load(r)
        q=next(q for q in s['questions'] if q['id']==id);self.assertEqual(q['status'],'draft');self.assertIn('<math',q['content']);self.assertEqual(s['updated_by'],'Agent')
        with self.request('/api/library',body={'action':'edit','id':id,'hashes':{id:q['content_sha256']},'text':{'content':'页面修改后的题干','answer':'2'},'revision':s['revision'],'request_id':uuid.uuid4().hex}) as r:self.assertTrue(json.load(r)['ok'])
        result=subprocess.run([sys.executable,str(SCRIPT),'--workspace',str(self.root),'show','--ids',id],capture_output=True,timeout=10)
        self.assertIn('页面修改后的题干',json.loads(result.stdout)['questions'][0]['content'])

    def test_library_upload_and_backup_require_local_auth(self):
        for path in ['/api/library','/api/backups','/pdf/012345678901234567890123/original.pdf']:
            with self.assertRaises(HTTPError) as e:self.request(path,{'X-Studio-Token':''},body={} if path=='/api/library' else None)
            self.assertEqual(e.exception.code,401)

if __name__=='__main__': unittest.main()
