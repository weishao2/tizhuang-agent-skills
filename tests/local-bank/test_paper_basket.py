import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parents[2] / 'skills/tizhuang-local-bank/scripts'))
import local_bank as lb

class PaperBasketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        lb.init(self.root / 'vault')
        self.bank = lb.Bank(self.root / 'vault')
        from PIL import Image
        Image.new('RGB', (80, 30), 'white').save(self.root / 'answer.png')
        for i in range(3):
            self.bank.save({'id': 'q'+str(i), 'content': '原题'+str(i)+' $x^2$', 'title': '题'+str(i), 'score': 5, 'status': 'draft' if i==2 else 'reviewed', 'answer': 'ANSWER_'+str(i)+' ![答案](answer.png)', 'analysis': 'ANALYSIS_'+str(i), 'assets': [{'path':'answer.png'}]}, self.root)
        self.path = self.root / 'basket.json'
        self.data = {'schema':'tizhuang.paper-basket/v1','request_id':'a'*32,'title':'分值与题序验收','duration_minutes':60,'answer_space_mm':12,'items':[{'question_id':'q1','score':7.5},{'question_id':'q0','score':0}]}
    def tearDown(self):
        self.tmp.cleanup()
    def build(self, confirm=False):
        self.path.write_text(json.dumps(self.data), encoding='utf-8')
        args = SimpleNamespace(basket=str(self.path),ids=None,count=None,plan=False,confirm_reviewed=confirm)
        return lb.paper(self.bank, args)
    def test_order_scores_snapshot_and_no_answer_leak(self):
        self.bank.questions(); before = {k:p.read_bytes() for k,p in self.bank.note_paths.items()}
        result = self.build(); manifest = lb.read_json(result['manifest'])
        self.assertEqual([i['question']['id'] for i in manifest['items']], ['q1','q0'])
        self.assertEqual([i['score'] for i in manifest['items']], [7.5,0]); self.assertEqual(result['score'],7.5)
        student = Path(result['student']).read_text(encoding='utf-8'); teacher = Path(result['teacher']).read_text(encoding='utf-8')
        self.assertNotIn('ANSWER_',student);self.assertNotIn('ANALYSIS_',student);self.assertIn('ANSWER_1',teacher)
        self.assertFalse((Path(result['student']).parent/'附件').exists())
        self.assertTrue((Path(result['teacher']).parent/'附件').exists())
        self.assertIn('60 分钟', student); self.assertIn('height:12mm',student)
        self.assertTrue(all(p.read_bytes()==before[k] for k,p in self.bank.note_paths.items()))
    def test_retry_returns_same_snapshot_and_changed_output_rejected(self):
        first=self.build();second=self.build();self.assertTrue(second['reused']);self.assertEqual(first['student'],second['student'])
        Path(first['student']).write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'发生变化'):self.build()
    def test_draft_requires_explicit_review_and_preserves_custom_notes(self):
        self.bank.questions(); path=self.bank.note_paths['q2'];text=path.read_text(encoding='utf-8').replace('---\n','---\n教师自定义: 保留\n',1)+'\n## 教师批注\n留存内容';path.write_text(text,encoding='utf-8')
        self.data['items']=[{'question_id':'q2','score':10}]
        with self.assertRaisesRegex(ValueError,'reviewed'):self.build()
        self.assertEqual(lb.read_note(path)['status'],'draft')
        self.build(True);self.assertEqual(lb.read_note(path)['status'],'reviewed');self.assertIn('教师自定义: 保留',path.read_text(encoding='utf-8'));self.assertIn('留存内容',path.read_text(encoding='utf-8'));self.assertEqual(lb.read_note(path)['score'],5)
    def test_invalid_scores_duplicates_missing_and_empty_stop(self):
        for value in [-1,1001,float('nan'),float('inf'),True,'5']:
            self.data['items']=[{'question_id':'q0','score':value}]
            with self.assertRaises(ValueError):self.build()
        for rows in [[],[{'question_id':'missing','score':5}],[{'question_id':'q0','score':5}]*2]:
            self.data['items']=rows
            with self.assertRaises(ValueError):self.build()
        self.assertFalse(list((self.bank.root/'试卷').glob('*/manifest.json')))
