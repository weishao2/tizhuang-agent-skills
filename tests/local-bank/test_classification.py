from pathlib import Path
from types import SimpleNamespace
import sys, tempfile, unittest, zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[2]/'skills/tizhuang-local-bank/scripts'))
import local_bank as lb
from teacher_library import classify

class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        lb.init(self.root); self.bank=lb.Bank(self.root)
        lb.atomic(self.root/'.bank/taxonomy/2-2.json',lb.json_text({'nodes':[{'id':10,'parent_id':0,'name':'函数'},{'id':11,'parent_id':10,'name':'反比例函数','knowledge_id':200}]}))
        lb.atomic(self.root/'.bank/taxonomy/2-3.json',lb.json_text({'nodes':[{'id':99,'parent_id':0,'name':'函数','knowledge_id':999}]}))
        self.bank.save({'id':'one','title':'函数面积','subject_id':2,'phase_id':2,'content':'图形面积 $6$。','answer':'待核答案','score':3,'tags':['我的标签']})
        self.bank.save({'id':'two','subject_id':2,'phase_id':2,'content':'另一道题。','tags':['第二题']})
        self.bank.questions();self.path=self.bank.note_paths['one']
        lb.atomic(self.path,self.path.read_text(encoding='utf-8')+'\n## 老师批注\n保留原文。\n')
        self.file=self.root/'plan.json'
        self.items=[]
        for q in self.bank.questions():
            self.items.append({'id':q['id'],'knowledge_tree_ids':['11'],'reason':'题目考查反比例函数。','expected_content_sha256':lb.digest('\n'.join(q[k] for k in ('content','answer','analysis')).encode())})
        self.write()
    def tearDown(self):self.tmp.cleanup()
    def write(self):lb.atomic(self.file,lb.json_text({'schema':'tizhuang.classification/v1','items':self.items}))
    def args(self,plan=False):return SimpleNamespace(file=self.file,plan=plan)
    def test_apply_preserves_content_metadata_and_is_idempotent(self):
        old={q['id']:q for q in self.bank.questions()}
        before=self.path.read_bytes()
        self.assertEqual(classify(self.bank,self.args(True))['action'],'plan')
        self.assertEqual(before,self.path.read_bytes())
        result=classify(self.bank,self.args());self.assertEqual(result['questions'],2)
        self.assertTrue(Path(result['backup']).exists())
        with zipfile.ZipFile(result['backup']) as z:self.assertEqual(z.read(self.path.relative_to(self.root).as_posix()),before)
        for q in self.bank.questions():
            for key in ['id','content','answer','analysis','source','score','status','edition_id','chapter_ids']:
                self.assertEqual(q.get(key),old[q['id']].get(key),key)
            self.assertEqual(q['knowledge_tree_ids'],['11']);self.assertEqual(q['knowledge_ids'],['200'])
            self.assertTrue(set(old[q['id']]['tags']).issubset(q['tags']))
        self.assertIn('保留原文',self.path.read_text(encoding='utf-8'))
        self.assertIn('反比例函数',self.path.read_text(encoding='utf-8'))
        self.assertEqual(len(self.bank.select(SimpleNamespace(subject=2,phase=2,knowledge=10))),2)
        after=self.path.read_bytes();self.assertEqual(classify(self.bank,self.args())['action'],'unchanged');self.assertEqual(after,self.path.read_bytes())
    def test_cross_scope_invalid_id_and_stale_body_rejected(self):
        before=self.path.read_bytes();self.items[-1]['knowledge_tree_ids']=['99'];self.write()
        with self.assertRaisesRegex(ValueError,'不属于'):classify(self.bank,self.args())
        self.assertEqual(before,self.path.read_bytes())
        self.items[-1]['knowledge_tree_ids']=['11'];self.items[-1]['expected_content_sha256']='stale';self.write()
        with self.assertRaisesRegex(ValueError,'内容已改变'):classify(self.bank,self.args())
        self.assertEqual(before,self.path.read_bytes())
    def test_preserves_existing_classification_and_extra_exact_ids(self):
        s=self.path.read_text(encoding='utf-8').replace('知识节点编号: []','知识节点编号: [10]').replace('精确知识编号: []','精确知识编号: [777]')
        lb.atomic(self.path,s);classify(self.bank,self.args())
        q=lb.read_note(self.path);self.assertEqual(q['knowledge_tree_ids'],['10','11']);self.assertEqual(q['knowledge_ids'],['777','200'])
    def test_write_failure_restores_notes_and_records(self):
        paths=list(self.bank.note_paths.values())+list((self.root/'.bank/records').glob('*.json'))
        before={p:p.read_bytes() for p in paths};atomic=lb.atomic;failed=False
        def fail_once(path,data):
            nonlocal failed
            if Path(path)==paths[1] and not failed:
                failed=True;raise OSError('write failure')
            atomic(path,data)
        with patch.object(lb,'atomic',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'write failure'):classify(self.bank,self.args())
        self.assertEqual(before,{p:p.read_bytes() for p in paths})
        self.assertEqual(classify(self.bank,self.args())['action'],'classified')

if __name__=='__main__':unittest.main()
