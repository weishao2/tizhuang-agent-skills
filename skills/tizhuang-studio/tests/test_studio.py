import concurrent.futures,copy,json,re,sys,tempfile,unittest,uuid,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import Workspace,Service,StudioError,prepare,normalize
import content

class FakeService:
    key='test-only-not-a-real-key'
    def __init__(self): self.calls=[]; self.remaining=50; self.member=None; self.timeout=False
    def meta(self,name,params):
        self.calls.append((name,params))
        return [{'id':100,'name':'函数','parent_id':None},{'id':101,'name':'一次函数','parent_id':100}]
    def quota(self): return {'remaining':self.remaining,'member_remaining':self.member}
    def get(self,path,params=None,protected=False):
        self.calls.append((path,params));
        if path=='/v1/local-bank/directory-quota': return {'scopes':[{'subject_id':2,'phase_id':2}]}
        if self.timeout: raise StudioError('连接未完成；可能已扣额。',502)
        return {'items':[{'id':123,'subject_id':2,'title_html':r'函数 \(y=2x+1\)，当 \(x=1\) 时求函数值。','question_type':'解答题','answer_html':'SECRET_ANSWER_3','analysis_html':'SECRET_ANALYSIS','subquestions':[{'title':'小题文本','answer':'CHILD_SECRET'}]}]}

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.service=FakeService(); self.w=Workspace(self.temp.name,self.service)
    def tearDown(self): self.temp.cleanup()
    def op(self,action,**kw): return self.w.operation({'action':action,'revision':self.w.state()['revision'],'request_id':uuid.uuid4().hex,**kw})
    def fetch(self): return self.op('fetch',subject_id=2,phase_id=2,count=1)
    def review(self):
        rows=self.w.state()['questions'];self.op('review',ids=[q['id'] for q in rows],hashes={q['id']:q['content_sha256'] for q in rows},confirm=True)
    def test_atomic_shared_revision(self):
        revision=self.w.state()['revision']
        def write(title):
            try: self.w.operation({'action':'settings','title':title,'revision':revision,'request_id':uuid.uuid4().hex}); return True
            except StudioError as e: return e.status
        with concurrent.futures.ThreadPoolExecutor(2) as pool: results=list(pool.map(write,['A','B']))
        self.assertCountEqual(results,[True,409]); self.assertEqual(self.w.state()['revision'],1)
    def test_idempotent_command(self):
        body={'action':'settings','title':'单次操作','revision':0,'request_id':uuid.uuid4().hex}
        a=self.w.operation(body); b=self.w.operation(body)
        self.assertEqual(a,b); self.assertEqual(self.w.state()['revision'],1)
    def test_basket_order_score_and_restart(self):
        self.op('demo'); ids=[q['id'] for q in self.w.state()['questions']][:3]
        self.op('add',ids=ids+ids); self.assertEqual(len(self.w.state()['items']),3)
        self.op('score',id=ids[1],score=12.5); self.op('move',id=ids[1],position=1)
        self.assertEqual(self.w.state()['items'][0],{'id':ids[1],'score':12.5})
        self.op('remove',id=ids[2]); restarted=Workspace(self.temp.name,self.service)
        self.assertEqual(restarted.state()['total_score'],17.5)
    def test_invalid_score_no_partial_write(self):
        self.fetch(); self.op('add',ids=['123']); before=self.w.state()
        for value in ['',True,float('nan'),float('inf'),-1,1001]:
            with self.assertRaises(StudioError): self.op('score',id='123',score=value)
        self.assertEqual(before,self.w.state())
    def test_no_paid_request_when_member_quota_short(self):
        self.service.member=0
        with self.assertRaises(StudioError): self.fetch()
        self.assertFalse(any(c[0]=='/v1/questions' for c in self.service.calls))
    def test_mutually_exclusive_filters(self):
        with self.assertRaises(StudioError): self.op('fetch',subject_id=2,phase_id=2,count=1,chapter_id=100,knowledge_tree_id=100)
        self.assertFalse(self.service.calls)
    def test_phase_is_preserved_with_no_chapter(self):
        self.fetch(); params=next(c[1] for c in self.service.calls if c[0]=='/v1/questions')
        self.assertEqual(params['knowledge_tree_ids'],['100']); self.assertEqual(len([c for c in self.service.calls if c[0]=='/v1/questions']),1)
        self.assertIn('SECRET_ANSWER_3',self.w.state()['questions'][0]['answer'])
    def test_timeout_is_not_retried(self):
        self.service.timeout=True
        b={'action':'fetch','subject_id':2,'phase_id':2,'count':1,'revision':0,'request_id':uuid.uuid4().hex}
        for _ in range(2):
            with self.assertRaises(StudioError): self.w.operation(b)
        self.assertEqual(len([c for c in self.service.calls if c[0]=='/v1/questions']),1)
    def test_unknown_knowledge_does_not_fetch(self):
        with self.assertRaises(StudioError): self.op('fetch',subject_id=2,phase_id=2,count=1,knowledge_tree_id=999)
        self.assertFalse(any(c[0]=='/v1/questions' for c in self.service.calls))
    def test_word_redacts_recursive_answers_and_is_editable(self):
        self.fetch(); self.op('add',ids=['123']); self.review(); self.op('export')
        export=self.w.state()['exports'][0]
        student=Path(self.temp.name)/export['student'].lstrip('/'); teacher=Path(self.temp.name)/export['teacher'].lstrip('/')
        with zipfile.ZipFile(student) as z: xml=z.read('word/document.xml').decode()
        self.assertNotIn('SECRET_',xml); self.assertNotIn('CHILD_SECRET',xml); self.assertIn('小题文本',xml); self.assertIn('m:oMath',xml)
        with zipfile.ZipFile(teacher) as z: xml=z.read('word/document.xml').decode()
        self.assertIn('SECRET_ANSWER_3',xml); self.assertIn('CHILD_SECRET',xml); self.assertIn('SECRET_ANALYSIS',xml)
    def test_real_demo_images_export_and_snapshot_stability(self):
        self.op('demo'); ids=[q['id'] for q in self.w.state()['questions']]; self.op('add',ids=ids); self.review(); self.op('export')
        ex=self.w.state()['exports'][0]; path=Path(self.temp.name)/ex['student'].lstrip('/'); old=path.read_bytes()
        with zipfile.ZipFile(path) as z:
            self.assertTrue(any(n.startswith('word/media/') for n in z.namelist()))
            self.assertIn('m:oMath',z.read('word/document.xml').decode())
        self.op('score',id=ids[0],score=20); self.assertEqual(old,path.read_bytes())
    def test_sanitizer_drops_active_content(self):
        clean=content.render('<script>evil()</script><img src="javascript:alert(1)" onerror="evil()"><p onclick="evil()">题目</p>','html')
        self.assertNotIn('evil',clean); self.assertNotIn('javascript:',clean); self.assertIn('题目',clean)
    def test_assets_cannot_escape_or_fetch_internal_network(self):
        for source in ['../secret','Assets/../../secret','http://127.0.0.1/key','https://evil.example/secret']:
            with self.assertRaises((ValueError,StudioError)):
                prepare({'content':f'<img src="{source}">','answer':'','analysis':''},Path(self.temp.name))
    def test_empty_basket_does_not_export(self):
        with self.assertRaises(StudioError): self.op('export')
        self.assertEqual(self.w.state()['exports'],[])

if __name__=='__main__': unittest.main()
