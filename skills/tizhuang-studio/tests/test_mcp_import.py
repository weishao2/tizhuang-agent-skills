import copy,json,sys,tempfile,unittest,uuid,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import Workspace,StudioError

def question(ident=701,solutions=True):
    q={'id':ident,'subject_id':2,'title_html':r'已知 \(y=2x+1\)，求函数值。','question_type':'解答题',
       'subquestions':[{'title':'当 x=1 时。','subquestions':[{'title':'写出计算步骤。'}]}]}
    if solutions:
        q['answer_html']='ANSWER_SEVEN'; q['analysis_html']='ANALYSIS_SEVEN'
        q['subquestions'][0]['subquestions'][0]['answer']='CHILD_ANSWER'
    return q

def envelope(rows): return {'content':[{'type':'text','text':json.dumps({'data':{'items':rows}})}],
                            'structuredContent':{'data':{'items':rows}},'isError':False}

class McpImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name); self.w=Workspace(self.root)
    def tearDown(self): self.temp.cleanup()
    def op(self,action,**extra):
        return self.w.operation(dict(action=action,revision=self.w.state()['revision'],request_id=uuid.uuid4().hex,actor='Agent',**extra))
    def body(self,**extra):
        return dict(action='import-mcp',revision=self.w.state()['revision'],request_id=uuid.uuid4().hex,actor='Agent',
                    subject_id=2,phase_id=2,auth_mode='oauth',tool='search_questions',result=envelope([question()]),add_to_basket=True,**extra)
    def test_oauth_and_api_key_same_basket_without_page_key(self):
        for mode,ident in [('oauth',701),('api_key',702)]:
            b=self.body(); b.update(auth_mode=mode,result=envelope([question(ident)]))
            with patch('engine.download',side_effect=AssertionError('Must not fetch questions')):
                result=self.w.operation(b)
            self.assertEqual(result['added_ids'],[str(ident)])
        state=Workspace(self.root).state()
        self.assertFalse(state['connected']); self.assertEqual(len(state['items']),2)
        self.assertEqual({q['mcp']['auth_mode'] for q in state['questions']},{'oauth','api_key'})
    def test_shapes_structured_text_core_and_jsonrpc_single(self):
        core={'data':{'items':[question()]}}
        shapes=[core,{'content':[{'type':'text','text':json.dumps(core)}]},envelope([question()])]
        for payload in shapes:
            b=self.body(); b['result']=payload; self.w.operation(b)
        b=self.body(); b.update(tool='get_question',result={'jsonrpc':'2.0','result':{'structuredContent':{'data':question(702)}}})
        self.w.operation(b); self.assertEqual(len(self.w.state()['questions']),2)
    def test_duplicate_import_preserves_scores_and_answers(self):
        body=self.body(); first=self.w.operation(body)
        self.assertEqual(self.w.operation(body),first)
        self.op('score',id='701',score=12)
        b=self.body(); b['result']=envelope([question(solutions=False)])
        result=self.w.operation(b)
        self.assertEqual(result['existing_ids'],['701']); self.assertEqual(result['added_ids'],[])
        self.assertEqual(self.w.state()['total_score'],12)
        self.assertIn('ANSWER_SEVEN',self.w.state()['questions'][0]['answer'])
    def test_hidden_answers_can_be_enriched_without_replacing_basket(self):
        b=self.body(); b['result']=envelope([question(solutions=False)])
        self.assertEqual(self.w.operation(b)['solutions_missing_ids'],['701'])
        with self.assertRaisesRegex(StudioError,'未返回答案'): self.op('export')
        self.op('score',id='701',score=9)
        self.assertEqual(self.w.operation(self.body())['updated_ids'],['701'])
        self.assertEqual(self.w.state()['total_score'],9)
        q=self.w.state()['questions'][0]
        self.w.operation({'action':'review','ids':[q['id']],'hashes':{q['id']:q['content_sha256']},'confirm':True,'revision':self.w.state()['revision'],'request_id':uuid.uuid4().hex})
        self.op('export'); ex=self.w.state()['exports'][0]
        for name in ['student','teacher']:
            with zipfile.ZipFile(self.root/ex[name].lstrip('/')) as z: xml=z.read('word/document.xml').decode()
            self.assertIn('写出计算步骤',xml); self.assertIn('m:oMath',xml)
            self.assertEqual('CHILD_ANSWER' in xml,name=='teacher')
            self.assertEqual('ANSWER_SEVEN' in xml,name=='teacher')
    def test_enrichment_cannot_replace_changed_stem(self):
        b=self.body(); b['result']=envelope([question(solutions=False)]); self.w.operation(b)
        before=self.w.state(); q=question(); q['title_html']='不同的题干'
        b=self.body(); b['result']=envelope([q])
        with self.assertRaises(StudioError): self.w.operation(b)
        self.assertEqual(before,self.w.state())
    def test_bad_batch_and_conflict_leave_no_partial_questions(self):
        for change in ['subject','phase','id','title','duplicate','revision']:
            q=question(702); b=self.body()
            if change=='subject': q['subject_id']=9
            elif change=='phase': q['phase_id']=9
            elif change=='id': q['id']='../../escape'
            elif change=='title': q.pop('title_html')
            elif change=='duplicate': q['id']=701; q['title_html']='不同'
            elif change=='revision': b['revision']=999
            b['result']=envelope([question(),q])
            with self.assertRaises(StudioError): self.w.operation(b)
            self.assertEqual(self.w.state()['questions'],[])
            self.assertEqual(self.w.state()['revision'],0)
    def test_credentials_errors_and_truncated_output_rejected(self):
        payloads=[{'isError':True,'structuredContent':{'error':{'message':'upstream'}}},
                  {'content':[{'type':'text','text':'truncated ...'}]},
                  {'data':{'items':[question()]},'access_token':'test-only-secret'},
                  {'data':{'items':[question()]},'extra':'tzo_a_'+'X'*32},
                  {'data':{'items':[]}}]
        for payload in payloads:
            b=self.body(); b['result']=payload
            with self.assertRaises(StudioError): self.w.operation(b)
            self.assertEqual(self.w.state()['questions'],[])
        self.assertNotIn('test-only-secret',(self.root/'studio.sqlite3').read_bytes().decode('latin1'))
    def test_images_localized_and_failed_images_not_added(self):
        from io import BytesIO
        from PIL import Image
        buf=BytesIO(); Image.new('RGB',(8,8),'white').save(buf,format='PNG')
        q=question(); q['title_html']+='<img src="https://tizhuang.qcscience.cc/test.png">'
        b=self.body(); b['result']=envelope([q])
        with patch('engine.download',return_value=buf.getvalue()) as get:
            self.w.operation(b); self.assertEqual(get.call_count,1)
        self.assertTrue(self.w.state()['questions'][0]['assets'])
        q=question(702); q['title_html']+='<img src="https://example.invalid/no.png">'
        b=self.body(); b['result']=envelope([q])
        r=self.w.operation(b)
        self.assertEqual(r['failed_ids'],['702']); self.assertEqual(r['added_ids'],[])
        self.assertTrue((self.root/'raw/702.json').exists())
    def test_save_only_does_not_change_basket(self):
        b=self.body(); b['add_to_basket']=False; self.w.operation(b)
        self.assertEqual(self.w.state()['items'],[]); self.assertEqual(len(self.w.state()['questions']),1)
    def test_missing_answer_fields_with_null_are_known_source_empty(self):
        q=question(solutions=False); q['answer_html']=None
        b=self.body(); b['result']=envelope([q]); self.w.operation(b)
        self.assertEqual(self.w.state()['questions'][0]['mcp']['solutions_status'],'included')

if __name__=='__main__': unittest.main()
