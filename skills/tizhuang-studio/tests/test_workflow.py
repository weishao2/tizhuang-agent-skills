import base64,json,sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import Workspace,StudioError,fetch_scope_key
from test_studio import FakeService
import library
from types import SimpleNamespace

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.service=FakeService();self.w=Workspace(self.tmp.name,self.service)
    def tearDown(self):self.tmp.cleanup()
    def op(self,action,**kw):return self.w.operation(dict(action=action,revision=self.w.state()['revision'],request_id=uuid.uuid4().hex,**kw))
    def fetch(self,**kw):return self.op('fetch',**(dict(subject_id=2,phase_id=2,count=5)|kw))
    def test_cursor_advances_actual_count_and_survives_restart(self):
        r=self.fetch();self.assertEqual(r['next_offset'],1)
        self.w=Workspace(self.tmp.name,self.service);self.fetch()
        self.assertEqual([p['offset'] for route,p in self.service.calls if route=='/v1/questions'],[0,1])
    def test_scopes_and_explicit_offsets_are_separate(self):
        self.fetch();self.fetch(knowledge_tree_id=101);self.fetch(offset=9)
        self.assertEqual([p['offset'] for route,p in self.service.calls if route=='/v1/questions'],[0,0,9])
        self.assertNotEqual(fetch_scope_key(dict(subject_id=2,phase_id=2)),fetch_scope_key(dict(subject_id=2,phase_id=3)))
    def test_failed_request_preserves_cursor_and_is_not_retried(self):
        self.fetch();before=self.w.state()['fetch_cursors'].copy();self.service.timeout=True
        body=dict(action='fetch',subject_id=2,phase_id=2,count=1,revision=self.w.state()['revision'],request_id=uuid.uuid4().hex)
        for _ in range(2):
            with self.assertRaises(StudioError):self.w.operation(body)
        self.assertEqual(self.w.state()['fetch_cursors'],before)
        self.assertEqual(len([x for x in self.service.calls if x[0]=='/v1/questions']),2)
    def test_cache_reuse_rechecks_entitlement_without_tree_download(self):
        self.fetch();self.service.calls.clear();self.fetch()
        self.assertFalse(any(route=='knowledge-points' for route,_ in self.service.calls))
        self.assertTrue(any(route=='/v1/local-bank/directory-quota' for route,_ in self.service.calls))
    def test_other_account_cache_cannot_bypass_scope_claim(self):
        self.fetch();old=self.service.get
        self.service.get=lambda path,params=None,protected=False: {'scopes':[]} if path.endswith('directory-quota') else old(path,params,protected)
        self.service.meta=lambda *a: (_ for _ in ()).throw(StudioError('无目录名额',403))
        with self.assertRaises(StudioError):self.fetch()
        self.assertEqual(len([x for x in self.service.calls if x[0]=='/v1/questions']),1)
    def test_permission_error_never_falls_back_to_cache(self):
        self.fetch();self.service.calls.clear()
        self.service.get=lambda *a,**k: (_ for _ in ()).throw(StudioError('Key 失效',401))
        with self.assertRaises(StudioError):self.fetch()
        self.assertFalse(self.service.calls)
    def test_chapter_cache_matches_edition(self):
        self.fetch(chapter_id=100,edition_id=4);self.service.calls.clear()
        self.fetch(chapter_id=101,edition_id=4)
        self.assertFalse(any(route=='chapters' for route,_ in self.service.calls))
        self.fetch(chapter_id=100,edition_id=5)
        self.assertEqual(len([x for x in self.service.calls if x[0]=='chapters']),1)
    def test_parent_tag_matches_children_without_prefix_collision(self):
        self.fetch();q=self.w.state()['questions'][0]
        q['tags']=['期中/易错'];self.w.save_question(q)
        args=SimpleNamespace(catalog=None,node=None,archived=False,status='',tag='期中',type='',unused=False,keyword='',limit=20)
        self.assertEqual(library.search(self.w.state(),args)['count'],1)
        args.tag='期';self.assertEqual(library.search(self.w.state(),args)['count'],0)
    def test_backup_restores_cursor_and_empty_response_does_not_skip(self):
        self.fetch();backup=self.op('backup')
        data=(self.w.root/backup['url'].lstrip('/')).read_bytes()
        self.fetch();self.op('restore',file_base64=base64.b64encode(data).decode(),confirm=True)
        self.assertEqual(list(self.w.state()['fetch_cursors'].values()),[1])
        old=self.service.get
        self.service.get=lambda path,params=None,protected=False: {'items':[]} if path=='/v1/questions' else old(path,params,protected)
        self.assertEqual(self.fetch()['next_offset'],1)

if __name__=='__main__':unittest.main()
