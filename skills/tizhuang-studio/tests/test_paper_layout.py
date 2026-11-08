import copy,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from lxml import html
from docx import Document
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from paper_layout import groups,grouped_manifest
from paper_html import render
from word_export import export_docx

class PaperLayoutTests(unittest.TestCase):
    def manifest(self):
        items=[]
        for n,(kind,score) in enumerate([('选择题',4),('填空题',3),('单选题',5),('解答题',7),('选择题',3.5)],1):
            items.append({'number':n,'score':score,'question':{'id':str(n),'type':kind,'content':f'<p>题干{n}</p>','answer':'<p>原答案</p>','analysis':'<p></p>','content_format':'html','assets':[]}})
        return {'title':'试卷','items':items,'duration_minutes':20,'total_score':22.5,'answer_space_mm':15}
    def test_group_totals_stable_order_and_no_mutation(self):
        m=self.manifest();old=copy.deepcopy(m);g=groups(m)
        self.assertEqual(g[0]['title'],'一、选择题（共 3 题，合计 12.5 分）')
        flat=grouped_manifest(m)['items'];self.assertEqual([i['question']['id'] for i in flat],['1','3','5','2','4'])
        self.assertEqual([i['number'] for i in flat],[1,2,3,4,5]);self.assertEqual(m,old)
    def test_html_word_share_group_headers_and_student_spaces(self):
        m=self.manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'out.docx';export_docx(SimpleNamespace(root=root),m,p,False,15)
            text='\n'.join(x.text for x in Document(p).paragraphs);doc=html.fromstring(render(root,m,False))
            for group in groups(m):self.assertIn(group['title'],text);self.assertIn(group['title'],doc.text_content())
            self.assertEqual(len(doc.xpath('//*[@class="answer-space"]')),1)
            self.assertNotIn('原答案',doc.text_content());self.assertIn('姓名',doc.text_content())
            first=doc.xpath('//section')[0];self.assertIn('1. （4 分）题干1',first.text_content())
    def test_teacher_omits_empty_analysis_and_keeps_original_answer(self):
        doc=html.fromstring(render(Path('.'),self.manifest(),True))
        self.assertEqual(doc.xpath('//h3/text()'),['答案']*5)
        self.assertEqual(doc.text_content().count('原答案'),5)
    def test_preview_options_keep_formula_and_use_four_columns(self):
        m=self.manifest();m['items']=m['items'][:1]
        m['items'][0]['question']['content']='<p>计算。</p><p>A. <math><mfrac><mn>1</mn><mn>6</mn></mfrac></math>　　B. 2　　C. 3　　D. 4</p>'
        doc=html.fromstring(render(Path('.'),m,False))
        self.assertEqual(len(doc.xpath('//*[@class="options cols-4"]/div')),4)
        self.assertEqual(len(doc.xpath('//mfrac')),1)

if __name__=='__main__':unittest.main()
