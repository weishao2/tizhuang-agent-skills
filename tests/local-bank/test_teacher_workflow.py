from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
import json
import yaml
import zipfile
sys.path.insert(0, str(Path(__file__).parents[2] / 'skills/tizhuang-local-bank/scripts'))
import local_bank as lb
import teacher_library as library
import pdf_import as pdf
from pdf_fixture import create


class TeacherWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.text, cls.scan, cls.double = create(cls.fixture.name)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / '题库'
        lb.init(self.root)
        self.bank = lb.Bank(self.root)
        tree = {'subject_id': 2, 'phase_id': 2, 'nodes': [{'id': 10, 'name': '数与式', 'parent_id': 0}, {'id': 11, 'name': '乘方', 'parent_id': 10, 'knowledge_id': 91}]}
        lb.atomic(self.root / '.bank/taxonomy/2-2.json', lb.json_text(tree))
        lb.atomic(self.root / '.bank/catalog/names.json', lb.json_text({'subjects': {'2':'数学'}, 'phases': {'2':'初中'}, 'editions': {}}))

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, file):
        return SimpleNamespace(file=file, subject=2, phase=2, edition=None, chapter=None)

    def test_organization_preserves_notes_ids_images_and_bases(self):
        # A small valid PNG is sufficient; preservation is asserted by its digest.
        from PIL import Image
        image = Path(self.tmp.name) / '图.png'
        Image.new('RGB', (20,20), 'white').save(image)
        q = {'id':'image-test','content':'![图](图.png)\n\n计算乘方。','title':'![图](https://example.test/image.png)','answer':'原答案','analysis':'原解析','subject_id':2,'phase_id':2,'tags':['用途/课堂例题'],'assets':[{'path':'图.png'}], 'original_payload':{'knowledges':'乘方'}}
        self.bank.save(q, image.parent)
        self.bank.questions()
        note = self.bank.note_paths['image-test']
        lb.atomic(note,note.read_text(encoding='utf-8')+'\n## 老师批注\n保留这段笔记。\n')
        lb.atomic(self.root / '未命名.base','views:\n  - type: table\n    name: 视图\n')
        lb.atomic(self.root / '我的视图.base','filters: 自定义\n')
        before = self.bank.questions()[0]
        result = library.organize(self.bank)
        after = self.bank.questions()[0]
        self.assertEqual(after['id'], before['id'])
        for key in ('content','answer','analysis','status','assets'):
            self.assertEqual(after[key],before[key])
        self.assertEqual(after['knowledge_tree_ids'],['11'])
        self.assertEqual(after['knowledge_ids'],['91'])
        target = self.bank.note_paths['image-test']
        self.assertIn('数与式',str(target))
        self.assertNotIn('https',target.name)
        self.assertIn('保留这段笔记',target.read_text(encoding='utf-8'))
        self.assertIn('tags:',target.read_text(encoding='utf-8'))
        self.assertFalse((self.root / '未命名.base').exists())
        self.assertTrue((self.root / '我的视图.base').exists())
        with zipfile.ZipFile(result['backup']) as z:
            self.assertIn('未命名.base',z.namelist())
        lb.verify_media(self.bank,after)
        self.assertEqual(library.organize(self.bank)['action'],'already_organized')

    def test_native_tags_edit_overrides_legacy_and_nested_search(self):
        self.bank.save({'id':'tagged','content':'计算题','tags':['旧标签']})
        self.bank.questions()
        path = self.bank.note_paths['tagged']
        text = path.read_text(encoding='utf-8').replace('tags:\n- 旧标签','标签:\n- 历史标签\ntags:\n- 用途/课堂例题')
        lb.atomic(path,text)
        q = self.bank.questions()[0]
        self.assertEqual(q['tags'],['用途/课堂例题'])
        self.assertEqual(len(self.bank.select(SimpleNamespace(tag='用途'))),1)

    def test_text_pdf_cross_page_answer_pairing_resume_and_draft_gate(self):
        library.organize(self.bank)
        prepared = pdf.prepare(self.bank,self.args(self.text))
        self.assertEqual(prepared['status'],'prepared')
        self.assertEqual(prepared['questions'],3)
        m = lb.read_json(prepared['manifest'])
        self.assertEqual([r['page'] for r in m['questions'][1]['content_regions']],[1,2])
        result = pdf.commit(self.bank,SimpleNamespace(batch=prepared['batch'],segmentation=None,image_draft=True))
        self.assertEqual(result['imported'],3)
        questions = self.bank.questions()
        self.assertTrue(all(q['status']=='draft' for q in questions))
        for q in questions:
            self.assertTrue(q['answer'])
            lb.verify_media(self.bank,q)
        first = next(q for q in questions if q['id'].endswith('-1'))
        self.assertNotIn('矩形',first['search_text'])
        self.assertEqual(len(self.bank.select(SimpleNamespace(query='矩形'))),1)
        pdf.commit(self.bank,SimpleNamespace(batch=prepared['batch'],segmentation=None,image_draft=True))
        self.assertEqual(len(self.bank.questions()),3)
        self.assertTrue(pdf.prepare(self.bank,self.args(self.text))['reused'])
        with self.assertRaisesRegex(ValueError,'核对'):
            lb.paper(self.bank,SimpleNamespace(ids=[first['id']],subject=None,phase=None,grade=None,edition=None,chapter=None,type=None,tag=None,status=None,knowledge=None,query=None,unused=False))

    def test_scanned_pdf_agent_regions_and_invalid_crop(self):
        library.organize(self.bank)
        original = pdf.prepare(self.bank,self.args(self.text))
        p = pdf.prepare(self.bank,self.args(self.scan))
        self.assertEqual(p['status'],'needs_agent')
        with self.assertRaisesRegex(ValueError,'Agent'):
            pdf.commit(self.bank,SimpleNamespace(batch=p['batch'],segmentation=None))
        # Model-assisted recognition supplies boxes in PDF points, using the visible original.
        candidates = lb.read_json(original['manifest'])['questions']
        for q in candidates:
            q['tags']=['用途/课堂例题']
            q['search_text']=q['title']
        candidates[0]['knowledge_tree_ids']=['11']
        segmentation = Path(self.tmp.name) / '识别.json'
        lb.atomic(segmentation,lb.json_text({'schema':pdf.LEGACY_SCHEMA,'questions':candidates}))
        result=pdf.commit(self.bank,SimpleNamespace(batch=p['batch'],segmentation=segmentation,image_draft=True))
        self.assertEqual(result['imported'],3)
        bad=lb.read_json(segmentation)
        mapped=next(q for q in self.bank.questions() if q['id'].endswith('-1'))
        self.assertEqual(mapped['knowledge_ids'],['91'])
        self.assertIn('考点/乘方',mapped['tags'])
        bad['questions'][0]['content_regions'][0]['bbox']=[0,0,99999,50]
        lb.atomic(segmentation,lb.json_text(bad))
        with self.assertRaisesRegex(ValueError,'边界'):
            pdf.commit(self.bank,SimpleNamespace(batch=p['batch'],segmentation=segmentation,image_draft=True))
        self.assertEqual(len(self.bank.questions()),3)

    def test_double_column_is_not_silently_auto_split(self):
        p=pdf.prepare(self.bank,self.args(self.double))
        self.assertEqual(p['status'],'needs_agent')


if __name__=='__main__':
    unittest.main()
