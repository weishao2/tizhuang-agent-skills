import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from PIL import Image
sys.path.insert(0, str(Path(__file__).parents[2] / 'skills/tizhuang-local-bank/scripts'))
import local_bank as lb

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
class WordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        lb.init(self.root/'vault'); self.bank=lb.Bank(self.root/'vault')
        Image.new('RGB',(240,90),'red').save(self.root/'question.webp')
        Image.new('RGB',(90,90),'blue').save(self.root/'answer.png')
    def tearDown(self): self.tmp.cleanup()
    def generate(self, content=None, fmt='markdown'):
        q={'id':'word-test','status':'reviewed','title':'可编辑数学题','content':content or r'求 $\frac{x^2}{2}+\sqrt{9}$。 ![题图](question.webp)','content_format':fmt,'answer':'PRIVATE_ANSWER ![解图](answer.png)','analysis':'PRIVATE_ANALYSIS','assets':[{'path':'question.webp'},{'path':'answer.png'}]}
        self.bank.save(q,self.root)
        return lb.paper(self.bank,SimpleNamespace(ids=['word-test'],count=None,title='Word 验收',plan=False,duration=45))
    def xml(self,path):
        z=zipfile.ZipFile(path); return z,etree.fromstring(z.read('word/document.xml'))
    def test_editable_math_embedded_images_no_solution_leak(self):
        result=self.generate()
        student,xml=self.xml(result['student_docx']); teacher,tx=self.xml(result['teacher_docx'])
        try:
            text=''.join(xml.xpath('//w:t/text()',namespaces=NS))
            self.assertFalse(etree.fromstring(student.read('word/styles.xml')).xpath('//w:style[@w:styleId="Title"]/w:pPr/w:pBdr',namespaces=NS));self.assertIn('求',text); self.assertIn('45 分钟',text)
            self.assertTrue(xml.xpath('//m:oMath//m:f',namespaces=NS)); self.assertTrue(xml.xpath('//m:rad',namespaces=NS))
            self.assertEqual(len([n for n in student.namelist() if n.startswith('word/media/')]),1)
            self.assertEqual(len([n for n in teacher.namelist() if n.startswith('word/media/')]),2)
            for name in student.namelist():
                self.assertNotIn(b'PRIVATE_',student.read(name))
            self.assertIn('PRIVATE_ANSWER',''.join(tx.xpath('//w:t/text()',namespaces=NS)))
            self.assertNotIn(b'TargetMode="External"',student.read('word/_rels/document.xml.rels'))
        finally: student.close();teacher.close()
    def test_html_table_superscript_and_list_remain_editable(self):
        result=self.generate('<p>选项 x<sup>2</sup>，H<sub>2</sub>O</p><table><tr><th>项目</th><th>数量</th></tr><tr><td>书</td><td>3</td></tr></table><ol><li>甲</li><li>乙</li></ol>', 'html')
        z,xml=self.xml(result['student_docx'])
        try:
            self.assertEqual(len(xml.xpath('//w:tbl',namespaces=NS)),1)
            self.assertTrue(xml.xpath('//w:vertAlign[@w:val="superscript"]',namespaces=NS))
            text=''.join(xml.xpath('//w:t/text()',namespaces=NS));self.assertIn('1. 甲',text);self.assertIn('2. 乙',text)
        finally:z.close()
    def test_corrupt_image_stops_instead_of_publishing_incomplete_word(self):
        (self.root/'question.webp').write_bytes(b'broken')
        with self.assertRaisesRegex(ValueError,'无法嵌入'): self.generate()
        self.assertFalse(list((self.bank.root/'试卷').glob('*/manifest.json')))
    def test_unsupported_formula_stops(self):
        from unittest.mock import patch
        with patch('docx_export.mathml2omml.convert',side_effect=ValueError('unsupported')):
            with self.assertRaisesRegex(ValueError,'第 1 题 · 题干：公式无法'): self.generate()
        self.assertFalse(list((self.bank.root/'试卷').glob('*/manifest.json')))

    def test_website_empty_answer_brackets_preserve_space_in_both_formats(self):
        blank='\u00a0'*5
        content='若 a+b=0，则 a=0，b=0。\\['+blank+'\\]；填空：'+blank+'。'
        result=self.generate(content)
        for key in ('student','teacher'):
            rendered=Path(result[key]).read_text(encoding='utf-8')
            self.assertIn('['+blank+']',rendered)
            self.assertNotIn('BANKMATHTOKEN',rendered)
        for key in ('student_docx','teacher_docx'):
            z,xml=self.xml(result[key])
            try:
                text=''.join(xml.xpath('//w:t/text()',namespaces=NS))
                self.assertIn('['+blank+']',text)
                self.assertIn('填空：'+blank+'。',text)
                self.assertFalse(xml.xpath('//m:oMath',namespaces=NS))
            finally:z.close()

    def test_blank_parentheses_and_real_display_math_coexist(self):
        rendered=lb.render(r'判断：\(   \)；计算：\[\frac{1}{2}\]。')
        self.assertIn('(   )',rendered)
        self.assertIn('<mfrac>',rendered)

    def test_invalid_teacher_formula_identifies_question_and_section(self):
        from unittest.mock import patch
        self.bank.save({'id':'bad-answer','status':'reviewed','title':'错误定位','content':'正常题干','answer':r'$\frac{$'})
        with patch('local_bank.mathml',side_effect=ValueError('invalid formula')):
            with self.assertRaisesRegex(ValueError,r'第 1 题 · 答案：公式无法转换'):
                lb.paper(self.bank,SimpleNamespace(ids=['bad-answer'],count=None,title='失败样例',plan=False,duration=45))
        self.assertFalse(list((self.bank.root/'试卷').glob('*/manifest.json')))
