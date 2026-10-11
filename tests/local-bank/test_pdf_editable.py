from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[2] / 'skills/tizhuang-local-bank/scripts'))
import local_bank as lb
import pdf_import as pdf
from pdf_fixture import create


class EditablePDFTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.source, _, _ = create(cls.fixture.name)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'vault'
        lb.init(self.root)
        self.bank = lb.Bank(self.root)
        self.prepared = pdf.prepare(self.bank, SimpleNamespace(file=self.source, subject=2, phase=2))
        self.items = lb.read_json(self.prepared['manifest'])['questions']
        for i, item in enumerate(self.items):
            item.update(content_markdown=['计算 $2^3$。\n\nA. $6$\n\nB. $8$', '矩形长 $6$，宽 $4$。\n\n{{figure:rectangle}}\n\n（1）求面积；（2）求周长。', '求一次函数 $y=2x+1$ 在 $x=3$ 时的值。'][i], answer_markdown=['B','面积 24，周长 20','7'][i], analysis_markdown='', figures=[])
        self.items[1]['figures'] = [{'id':'rectangle','page':1,'bbox':[70,358,280,510]}]
        self.seg = Path(self.tmp.name) / 'checked.json'

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, **kw):
        return SimpleNamespace(batch=self.prepared['batch'], segmentation=self.seg, **kw)

    def save_seg(self):
        lb.atomic(self.seg, lb.json_text({'schema':pdf.SCHEMA,'questions':self.items}))

    def legacy(self):
        pdf.commit(self.bank, SimpleNamespace(batch=self.prepared['batch'],segmentation=None,image_draft=True))

    def test_default_no_silent_image_import_and_native_body(self):
        with self.assertRaisesRegex(ValueError, 'v2'):
            pdf.commit(self.bank, SimpleNamespace(batch=self.prepared['batch'],segmentation=None))
        self.assertEqual(len(self.bank.questions()),0)
        self.save_seg()
        self.assertEqual(pdf.commit(self.bank,self.args())['imported'],3)
        rows = self.bank.questions()
        self.assertEqual(sum(len(q['assets']) for q in rows),1)
        self.assertTrue(all('$' in q['content'] and '原题第' not in q['content'] for q in rows))
        self.assertTrue(all(q['status']=='draft' for q in rows))
        for q in rows: lb.verify_media(self.bank,q)
        pdf.commit(self.bank,self.args())
        self.assertEqual(len(self.bank.questions()),3)
        self.items[0]['answer_markdown']='不同答案'
        self.save_seg()
        with self.assertRaisesRegex(ValueError,'答案或解析不同'):
            pdf.commit(self.bank,self.args())

    def test_upgrade_preserves_teacher_metadata_extra_text_and_paths(self):
        self.legacy()
        old = self.bank.questions()
        paths = dict(self.bank.note_paths)
        for q in old:
            path=paths[q['id']]
            lb.atomic(path,path.read_text(encoding='utf-8').replace('tags:\n- PDF导入','tags:\n- PDF导入\n- 老师标签')+'\n## 教师批注\n这一段必须保留。\n')
        self.save_seg()
        result=pdf.commit(self.bank,self.args(upgrade_to_editable=True))
        self.assertEqual(result['imported'],3)
        current = self.bank.questions()
        self.assertEqual(paths,self.bank.note_paths)
        self.assertEqual({q['id'] for q in old},{q['id'] for q in current})
        for q in current:
            self.assertIn('老师标签',q['tags'])
            self.assertIn('这一段必须保留',paths[q['id']].read_text(encoding='utf-8'))
        before = {p:p.read_bytes() for p in paths.values()}
        pdf.commit(self.bank,self.args(upgrade_to_editable=True))
        self.assertEqual(before,{p:p.read_bytes() for p in paths.values()})
        self.assertTrue(list((Path(self.prepared['manifest']).parent/'backups').glob('*.zip')))

    def test_upgrade_rejects_body_edit_and_reviewed_without_partial_changes(self):
        self.legacy()
        rows=self.bank.questions()
        path=self.bank.note_paths[rows[-1]['id']]
        lb.atomic(path,path.read_text(encoding='utf-8').replace('<!-- bank:content:end -->','老师改了题干\n<!-- bank:content:end -->'))
        before={p:p.read_bytes() for p in self.bank.note_paths.values()}
        self.save_seg()
        with self.assertRaisesRegex(ValueError,'老师已修改'):
            pdf.commit(self.bank,self.args(upgrade_to_editable=True))
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        lb.atomic(path,path.read_text(encoding='utf-8').replace('老师改了题干\n','').replace('待核对','已核对'))
        with self.assertRaisesRegex(ValueError,'已核对'):
            pdf.commit(self.bank,self.args(upgrade_to_editable=True))

    def test_upgrade_failure_rolls_back_managed_files(self):
        self.legacy()
        self.bank.questions()
        tracked=list(self.bank.note_paths.values())+list((self.root/'.bank/records').glob('*.json'))
        before={p:p.read_bytes() for p in tracked}
        self.save_seg()
        atomic=lb.atomic
        target=tracked[1]
        failed=False
        def fail_once(path,data):
            nonlocal failed
            if Path(path)==target and not failed:
                failed=True
                raise OSError('simulated write interruption')
            return atomic(path,data)
        with patch.object(lb,'atomic',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'simulated'):
                pdf.commit(self.bank,self.args(upgrade_to_editable=True))
        self.assertEqual(before,{p:p.read_bytes() for p in tracked})
        pdf.commit(self.bank,self.args(upgrade_to_editable=True))

    def test_bad_figure_and_original_question_number_rejected(self):
        self.items[1]['content_markdown']='矩形 {{figure:missing}}'
        self.save_seg()
        with self.assertRaisesRegex(ValueError,'配图'):
            pdf.commit(self.bank,self.args())
        self.items[1]['content_markdown']='2. 矩形 {{figure:rectangle}}'
        self.save_seg()
        with self.assertRaisesRegex(ValueError,'原卷题号'):
            pdf.commit(self.bank,self.args())
        self.assertEqual(len(self.bank.questions()),0)


if __name__=='__main__': unittest.main()
