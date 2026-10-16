from pathlib import Path
from types import SimpleNamespace
import sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).parents[2]/'skills/tizhuang-local-bank/scripts'))
import local_bank as lb
from auto_classify import run
from paper_links import repair


class AutomaticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        lb.init(self.root); self.bank = lb.Bank(self.root)
        lb.atomic(self.root/'.bank/taxonomy/2-2.json', lb.json_text({'nodes': [{'id': 11, 'name': '反比例函数', 'parent_id': 0, 'knowledge_id': 500}, {'id': 12, 'name': '圆', 'parent_id': 0}]}))
    def tearDown(self): self.temp.cleanup()
    def save(self, **values):
        return self.bank.save({'id': 'one', 'content': '含有圆字的文本不能直接匹配圆', 'subject_id': 2, 'phase_id': 2, **values})
    def test_exact_tags_only_and_idempotent(self):
        self.save(tags=['考点/反比例函数']); before=self.bank.questions()[0]
        result=run(self.bank,SimpleNamespace());self.assertEqual(result['classified'],1)
        after=self.bank.questions()[0];self.assertEqual(after['knowledge_ids'],['500'])
        for key in ['content','answer','analysis','status','edition_id','chapter_ids']:self.assertEqual(before.get(key),after.get(key))
        self.assertEqual(run(self.bank,SimpleNamespace())['considered'],0)
    def test_missing_tree_ambiguous_tags_and_stem_only_remain_pending(self):
        self.save();self.save(id='other',phase_id=3,tags=['圆'])
        result=run(self.bank,SimpleNamespace());self.assertEqual(result['pending'],2);self.assertEqual(result['classified'],0)
        lb.atomic(self.root/'.bank/taxonomy/2-2.json',lb.json_text({'nodes':[{'id':1,'parent_id':0,'name':'圆'},{'id':2,'parent_id':0,'name':'圆'}]}))
        self.save(id='third',content='另一个题干',tags=['圆'])
        result=run(self.bank,SimpleNamespace());self.assertEqual(result['pending'],3)
    def test_selected_ids_do_not_touch_others(self):
        self.save(tags=['反比例函数']);self.save(id='two',content='另一题',tags=['圆'])
        result=run(self.bank,SimpleNamespace(ids=['one']));self.assertEqual(result['classified'],1)
        self.assertFalse({q['id']:q for q in self.bank.questions()}['two']['knowledge_tree_ids'])
    def test_punctuation_in_catalog_matches_native_tags_without_guessing_collisions(self):
        lb.atomic(self.root/'.bank/taxonomy/2-2.json',lb.json_text({'nodes':[{'id':1,'parent_id':0,'name':'有理数的乘方（二）'}]}))
        self.save(tags=['考点/有理数的乘方（二）'])
        self.assertEqual(run(self.bank,SimpleNamespace())['classified'],1)
        lb.atomic(self.root/'.bank/taxonomy/2-2.json',lb.json_text({'nodes':[{'id':1,'parent_id':0,'name':'乘方（二）'},{'id':2,'parent_id':0,'name':'乘方(二)'}]}))
        self.save(id='two',content='另一题',tags=['考点/乘方（二）'])
        result=run(self.bank,SimpleNamespace(ids=['two']))
        self.assertEqual(result['classified'],0)
        self.assertEqual(result['pending'],1)
    def test_repair_empty_notes_keeps_real_files_and_backup(self):
        folder=self.root/'试卷/demo';folder.mkdir(parents=True)
        lb.atomic(folder/'manifest.json',lb.json_text({'title':'练习'}))
        lb.atomic(folder/'试卷.md','# 练习\n[打印](试卷/历史打印稿/试卷.html)')
        lb.atomic(folder/'打印稿/试卷.html','<h1>真实试卷</h1>')
        history=self.root/'试卷/历史打印稿'
        lb.atomic(history/'试卷.html 1.md','');lb.atomic(history/'试卷.html 2.md','老师记录')
        result=repair(self.bank);self.assertEqual(result['archived_empty'],1)
        self.assertTrue(Path(result['backup']).exists());self.assertEqual((history/'试卷.html 2.md').read_text(encoding='utf-8'),'老师记录')
        self.assertIn('](打印稿/试卷.html)',(folder/'试卷.md').read_text(encoding='utf-8'));self.assertEqual(repair(self.bank)['repaired'],0)


if __name__=='__main__':unittest.main()
