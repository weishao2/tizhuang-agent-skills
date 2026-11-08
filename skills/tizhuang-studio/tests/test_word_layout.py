import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from docx import Document
from word_export import export_docx


class WordLayoutTests(unittest.TestCase):
    def render(self, kind='选择题', teacher=False, choices=None):
        q = dict(type=kind, assets=[], content_format='html',
                 content='<p>计算 <math><mfrac><mn>1</mn><mn>6</mn></mfrac></math>。</p><p>' + (choices or 'A. 1　　B. 2　　C. 3　　D. 4') + '</p>',
                 answer='<div><span></span></div>', analysis='<div><span></span></div>')
        manifest = dict(title='排版测试', total_score=5, duration_minutes=20,
                        items=[dict(number=1, score=5, question=q)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'paper.docx'
            export_docx(SimpleNamespace(root=Path(tmp)), manifest, path, teacher, 25)
            return Document(path)

    def test_inline_number_editable_formula_and_aligned_options(self):
        doc = self.render()
        p = next(p for p in doc.paragraphs if p.text.startswith('1.'))
        self.assertIn('计算', p.text)
        self.assertTrue(p._p.xpath('.//m:oMath'))
        choices = next(p for p in doc.paragraphs if p.text.startswith('A.'))
        self.assertEqual(len(choices._p.xpath('./w:r/w:tab')), 3)
        self.assertNotIn('无答案试卷', '\n'.join(p.text for p in doc.paragraphs))
        self.assertFalse(any(p.paragraph_format.space_after and p.paragraph_format.space_after.mm >= 24.9 for p in doc.paragraphs))

    def test_long_choices_wrap_and_subjective_questions_keep_answer_space(self):
        doc = self.render('解答题', choices='　　'.join(f'{c}. ' + '这是较长选项内容' * 2 for c in 'ABCD'))
        options = next(p for p in doc.paragraphs if p.text.startswith('A.'))
        self.assertEqual(len(options._p.xpath('.//w:br')), 1)
        self.assertEqual(len(options._p.xpath('./w:r/w:tab')), 2)
        self.assertTrue(any(p.paragraph_format.space_after and p.paragraph_format.space_after.mm >= 24.9 for p in doc.paragraphs))

    def test_empty_html_answer_is_explicit_without_empty_analysis_heading(self):
        text = '\n'.join(p.text for p in self.render(teacher=True).paragraphs)
        self.assertIn('原题未提供答案', text)
        self.assertNotIn('解析', text)


if __name__ == '__main__':
    unittest.main()
