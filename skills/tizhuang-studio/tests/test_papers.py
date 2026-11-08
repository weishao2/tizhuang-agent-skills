import copy, hashlib, json, sys, tempfile, unittest, uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import Workspace, StudioError

class PaperTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.w=Workspace(self.root)
        self.ident='20261108-172700-abcdef12'
        self.q={'id':'one','content':'Current text','answer':'3','analysis':'','subject_id':2,'phase_id':2,'status':'draft','assets':[]}
        self.w.save_question(self.q)
        folder=self.root/'exports'/self.ident;folder.mkdir(parents=True)
        snapshot={'title':'Original','duration_minutes':20,'answer_space_mm':15,'items':[{'score':7,'question':{**self.q,'content':'Old text','status':'reviewed'}}]}
        (folder/'snapshot.json').write_text(json.dumps(snapshot),encoding='utf-8')
        (folder/'student.docx').write_bytes(b'original-export')
        with self.w.connect() as db:
            s=json.loads(db.execute('SELECT data FROM state').fetchone()[0]);s['exports']=[{'id':self.ident,'title':'Original','count':1,'question_ids':['one']}]
            db.execute('UPDATE state SET data=?',(json.dumps(s),))
    def tearDown(self):self.temp.cleanup()
    def op(self,action,**kw):return self.w.operation({'action':action,'id':self.ident,'revision':self.w.state()['revision'],'request_id':uuid.uuid4().hex,**kw})
    def test_labels_persist_without_changing_questions_basket_or_files(self):
        before=self.w.state();files={p:p.read_bytes() for p in (self.root/'exports').rglob('*') if p.is_file()}
        self.op('paper-update',title='期中 A 卷',tags=['期中','A 卷','期中'])
        after=Workspace(self.root).state();self.assertEqual(after['exports'][0]['tags'],['期中','A 卷']);self.assertEqual(after['exports'][0]['display_title'],'期中 A 卷')
        self.assertEqual(before['questions'],after['questions']);self.assertEqual(before['items'],after['items']);self.assertEqual(files,{p:p.read_bytes() for p in files})
    def test_invalid_metadata_is_atomic(self):
        before=self.w.state()
        for kw in ({'title':'','tags':[]},{'title':'Valid','tags':'string'},{'title':'Valid','tags':['x'*25]}):
            with self.assertRaises(StudioError):self.op('paper-update',**kw)
        self.assertEqual(before,self.w.state())
    def test_reopen_requires_confirmation_and_keeps_current_question_review_state(self):
        before=self.w.state()
        with self.assertRaises(StudioError):self.op('paper-open')
        self.assertEqual(before,self.w.state())
        self.op('paper-update',title='New name',tags=['复习']);self.op('paper-open',confirm=True)
        s=self.w.state();self.assertEqual(s['items'],[{'id':'one','score':7}]);self.assertEqual(s['title'],'New name');self.assertEqual(s['duration_minutes'],20)
        self.assertEqual(s['questions'],before['questions']);self.assertEqual(s['questions'][0]['status'],'draft');self.assertEqual(s['previous_basket']['items'],[])
        with self.assertRaises(StudioError):self.op('export')
    def test_missing_or_archived_question_cannot_replace_basket(self):
        self.w.save_question({**self.q,'archived':True});before=self.w.state()
        with self.assertRaises(StudioError):self.op('paper-open',confirm=True)
        self.assertEqual(before,self.w.state())
    def test_missing_snapshot_has_safe_summary_and_cannot_replace_basket(self):
        (self.root/'exports'/self.ident/'snapshot.json').unlink();s=self.w.state();self.assertFalse(s['exports'][0]['snapshot_available'])
        with self.assertRaises(StudioError):self.op('paper-open',confirm=True)
        self.assertEqual(self.w.state()['items'],[])
    def test_stale_revision_cannot_replace_basket(self):
        self.op('settings',title='Keep me')
        with self.assertRaises(StudioError):self.w.operation({'action':'paper-open','id':self.ident,'confirm':True,'revision':0,'request_id':uuid.uuid4().hex})
        self.assertEqual(self.w.state()['title'],'Keep me')
    def test_summary_does_not_write_state(self):
        with self.w.connect() as db:before=db.execute('SELECT data FROM state').fetchone()[0]
        e=self.w.state()['exports'][0];self.assertEqual(e['total_score'],7);self.assertEqual(e['scopes'],[{'phase_id':'2','subject_id':'2'}])
        with self.w.connect() as db:self.assertEqual(before,db.execute('SELECT data FROM state').fetchone()[0])

if __name__=='__main__':unittest.main()
