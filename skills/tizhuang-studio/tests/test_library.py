import base64,copy,json,sys,tempfile,unittest,uuid,zipfile
from io import BytesIO
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import Workspace,StudioError
import library,content

def pdf_fixture():
    # A small readable vector PDF fixture with an outer question number and a separate diagram.
    stream=b'BT /F1 16 Tf 50 760 Td (1. Find x when x + 2 = 5. See figure.) Tj ET 50 560 m 150 660 l 250 560 l h S BT /F1 12 Tf 130 540 Td (Figure 1) Tj ET BT /F1 16 Tf 50 450 Td (Answer: x = 3.) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    data=b'%PDF-1.4\n';offsets=[0]
    for n,obj in enumerate(objects,1):offsets.append(len(data));data+=f'{n} 0 obj\n'.encode()+obj+b'\nendobj\n'
    start=len(data);data+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    for offset in offsets[1:]:data+=f'{offset:010d} 00000 n \n'.encode()
    return data+f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode()

class LibraryTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.w=Workspace(self.root)
    def tearDown(self):self.temp.cleanup()
    def op(self,action,**extra):return self.w.operation({'action':action,'revision':self.w.state()['revision'],'request_id':uuid.uuid4().hex,**extra})
    def create(self,**extra):return self.op('create',subject_id=2,phase_id=2,text={'content':'求 $x+2=5$ 中的 $x$。','answer':'ANSWER_ONLY_3','analysis':'减去 2。'},**extra)['id']
    def q(self,id):return next(q for q in self.w.state()['questions'] if q['id']==id)
    def hashes(self,ids):return {id:self.q(id)['content_sha256'] for id in ids}
    def tree(self,**extra):return self.op('catalog-save',kind='knowledge',subject_id=2,phase_id=2,label='初中数学知识点',nodes=[{'id':10,'name':'方程','parent_id':None},{'id':11,'name':'一元一次方程','parent_id':10}],**extra)
    def review(self,ids):return self.op('review',ids=ids,hashes=self.hashes(ids),confirm=True)
    def archive_data(self,result):return base64.b64encode((self.root/result['url'].lstrip('/')).read_bytes()).decode()
    def test_tree_persisted_and_parent_descendants(self):
        self.tree();c=Workspace(self.root).state()['catalogs'][0];self.assertEqual(library.descendants(c,'10'),{'10','11'});self.assertEqual(c['label'],'初中数学知识点')
    def test_tree_cycles_duplicate_and_cross_scope_rejected(self):
        for nodes in [[{'id':1,'name':'x','parent_id':2},{'id':2,'name':'y','parent_id':1}],[{'id':1,'name':'x'},{'id':1,'name':'y'}],[{'id':1,'name':'x','parent_id':99}]]:
            with self.assertRaises(StudioError):self.op('catalog-save',kind='knowledge',subject_id=2,phase_id=2,nodes=nodes)
        id=self.create()
        with self.assertRaises(StudioError):self.op('classify',ids=[id],hashes=self.hashes([id]),knowledge_tree_ids=['11'])
        self.assertEqual(self.q(id)['knowledge_tree_ids'],[])
    def test_classification_tags_and_chapters(self):
        self.tree();id=self.create();self.op('catalog-save',kind='chapter',subject_id=2,phase_id=2,edition_id=21,label='教材测试目录',nodes=[{'id':3,'name':'第一章'}])
        self.op('classify',ids=[id],hashes=self.hashes([id]),knowledge_tree_ids=['11'],chapter_ids=['3'],edition_id=21,tags=['期末','重点'])
        q=self.q(id);self.assertEqual(q['knowledge_tree_ids'],['11']);self.assertEqual(q['chapter_ids'],['3']);self.assertEqual(self.w.state()['library_stats']['unclassified'],0)
        with self.assertRaises(StudioError):self.op('classify',ids=[id],hashes=self.hashes([id]),edition_id=22,chapter_ids=['3'])
    def test_catalog_update_cannot_orphan_existing_questions(self):
        self.tree();id=self.create();self.op('classify',ids=[id],hashes=self.hashes([id]),knowledge_tree_ids=['11'])
        with self.assertRaises(StudioError):self.op('catalog-save',kind='knowledge',subject_id=2,phase_id=2,nodes=[{'id':10,'name':'方程'}],replace=True)
        self.assertEqual(len(self.w.state()['catalogs'][0]['nodes']),2)
    def test_auto_classification_exact_only(self):
        self.tree();id=self.create();self.op('classify',ids=[id],hashes=self.hashes([id]),tags=['一元一次方程'])
        other=self.create();r=self.op('auto-classify');self.assertEqual(r['classified_ids'],[id]);self.assertEqual(r['remaining_ids'],[other]);self.assertEqual(self.q(id)['status'],'draft')
    def test_edit_invalidates_review_and_stale_hash(self):
        id=self.create();self.review([id]);old=self.hashes([id]);self.op('edit',id=id,hashes=old,text={'content':'求 $x+1=3$。','answer':'2'},notes='课堂讨论')
        self.assertEqual(self.q(id)['status'],'draft');self.assertIn('<math',self.q(id)['content']);self.assertTrue(list((self.root/'history').glob('*.json')))
        with self.assertRaises(StudioError):self.op('review',ids=[id],hashes=old,confirm=True)
    def test_agent_cannot_self_review_and_draft_export_blocked(self):
        id=self.create();self.op('add',ids=[id])
        with self.assertRaises(StudioError):self.op('export')
        with self.assertRaises(StudioError):self.op('review',ids=[id],hashes=self.hashes([id]),confirm=True,actor='Agent')
    def test_review_only_requested_rows_and_archive_retains_question(self):
        a,b=self.create(),self.create();self.review([a]);self.assertEqual(self.q(b)['status'],'draft')
        self.op('archive',ids=[a],hashes=self.hashes([a]),confirm=True);self.assertEqual(len(self.w.state()['questions']),2);self.assertEqual(self.w.state()['library_stats']['total'],1)
        self.op('archive',ids=[a],hashes=self.hashes([a]),confirm=True,archived=False);self.assertEqual(self.w.state()['library_stats']['total'],2)
    def test_print_and_word_same_snapshot_without_solution_leak(self):
        id=self.create();self.review([id]);self.op('add',ids=[id]);self.op('export');s=self.w.state();e=s['exports'][0]
        student=(self.root/e['student_html'].lstrip('/')).read_text(encoding='utf-8');teacher=(self.root/e['teacher_html'].lstrip('/')).read_text(encoding='utf-8')
        self.assertNotIn('ANSWER_ONLY',student);self.assertIn('ANSWER_ONLY',teacher);self.assertIn('<math',student);self.assertEqual(e['question_ids'],[id]);self.assertEqual(s['library_stats']['unused'],0)
    def test_backup_restore_basket_catalog_and_excludes_session(self):
        self.tree();a=self.create();self.op('add',ids=[a]);self.op('score',id=a,score=9)
        (self.root/'session.json').write_text('NOT_A_REAL_TOKEN');r=self.op('backup');data=self.archive_data(r)
        with zipfile.ZipFile(BytesIO(base64.b64decode(data))) as z:self.assertFalse(any('session' in n or 'sqlite' in n for n in z.namelist()))
        self.op('score',id=a,score=3);self.create();restored=self.op('restore',file_base64=data,confirm=True)
        self.assertEqual(self.w.state()['total_score'],9);self.assertEqual(len(self.w.state()['questions']),1);self.assertEqual(len(self.w.state()['catalogs']),1);self.assertTrue((self.root/restored['before_restore_backup']['url'].lstrip('/')).is_file())
    def test_package_merge_duplicate_and_no_answers(self):
        id=self.create();r=self.op('package-export',ids=[id],include_solutions=False);data=self.archive_data(r)
        with zipfile.ZipFile(BytesIO(base64.b64decode(data))) as z:self.assertNotIn('ANSWER_ONLY',z.read('manifest.json').decode())
        self.assertEqual(self.op('package-import',file_base64=data)['imported_ids'],[])
        with tempfile.TemporaryDirectory() as other:
            w=Workspace(other);r=w.operation({'action':'package-import','file_base64':data,'revision':0,'request_id':uuid.uuid4().hex});self.assertEqual(r['imported_ids'],[id]);self.assertEqual(w.state()['questions'][0]['status'],'draft')
    def test_legacy_local_bank_package_import(self):
        q={'id':'old-test','subject_id':2,'phase_id':2,'content':'求 $x=1$','answer':'1','analysis':'','content_format':'markdown','knowledge_tree_ids':['99'],'chapter_ids':['88'],'assets':[]}
        out=BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('questions.json',json.dumps({'schema':'tizhuang.question-package/v1','questions':[q],'includes_solutions':True}))
        self.op('package-import',file_base64=base64.b64encode(out.getvalue()).decode());self.assertIn('<math',self.q('old-test')['content']);self.assertEqual(self.q('old-test')['unmapped_chapter_ids'],['88'])
    def test_zip_traversal_and_tamper_rejected_without_data_changes(self):
        self.create();before=self.w.state()
        for name in ['../session.json','/etc/file','Assets\\bad.png','raw/../session.json']:
            out=BytesIO()
            with zipfile.ZipFile(out,'w') as z:z.writestr(name,'x')
            with self.assertRaises(StudioError):self.op('package-import',file_base64=base64.b64encode(out.getvalue()).decode())
        self.assertEqual(before,self.w.state())
    def test_pdf_original_pages_editable_import_and_idempotence(self):
        self.tree();r=self.op('pdf-prepare',file_base64=base64.b64encode(pdf_fixture()).decode(),filename='fixture.pdf',subject_id=2,phase_id=2);batch=r['batch_id'];pages=self.w.state()['pdf_batches'][0]['pages'];self.assertIn('Find x',pages[0]['text']);self.assertTrue((self.root/'pdf'/batch/pages[0]['image']).is_file())
        plan={'schema':'tizhuang.pdf-segmentation/v2','questions':[{'number':'1','type':'解答题','content_markdown':'1. 求 $x+2=5$ 中的 $x$。\n\n{{figure:triangle}}','answer_markdown':'3','analysis_markdown':'两边减去 2。','knowledge':'一元一次方程','content_regions':[{'page':1,'bbox':[40,60,500,300]}],'answer_regions':[{'page':1,'bbox':[40,360,300,410]}],'figures':[{'id':'triangle','page':1,'bbox':[40,170,260,290]}]}]}
        result=self.op('pdf-import',batch_id=batch,plan=plan);q=self.q(result['imported_ids'][0]);self.assertEqual(q['knowledge_tree_ids'],['11']);self.assertEqual(q['status'],'draft');self.assertFalse(q['editable']['content'].startswith('1.'));self.assertIn('<math',q['content']);self.assertEqual(len(q['assets']),1)
        repeated=self.op('pdf-import',batch_id=batch,plan=plan);self.assertEqual(repeated['existing_ids'],[q['id']]);self.assertEqual(len(self.w.state()['questions']),1)
        self.assertTrue(self.op('pdf-prepare',file_base64=base64.b64encode(pdf_fixture()).decode(),subject_id=2,phase_id=2)['existing'])
    def test_pdf_refuses_whole_question_image_and_bad_regions(self):
        b=self.op('pdf-prepare',file_base64=base64.b64encode(pdf_fixture()).decode(),subject_id=2,phase_id=2)['batch_id']
        for text,box in [('{{figure:all}}',[0,0,595,842]),('文字 {{figure:all}}',[-1,0,595,842]),('文字 {{figure:all}}',[0,0,595,842])]:
            with self.assertRaises(StudioError):self.op('pdf-import',batch_id=b,plan={'schema':'tizhuang.pdf-segmentation/v2','questions':[{'number':'1','content_markdown':text,'content_regions':[{'page':1,'bbox':[0,0,500,500]}],'figures':[{'id':'all','page':1,'bbox':box}]}]})
        self.assertEqual(self.w.state()['questions'],[])

    def test_scanned_pdf_prepares_without_inventing_text_or_questions(self):
        from PIL import Image
        buf=BytesIO();Image.new('RGB',(100,150),'white').save(buf,'PDF')
        self.op('pdf-prepare',file_base64=base64.b64encode(buf.getvalue()).decode(),subject_id=2,phase_id=2)
        page=self.w.state()['pdf_batches'][0]['pages'][0];self.assertTrue(page['needs_visual_reading']);self.assertEqual(page['text'],'');self.assertEqual(self.w.state()['questions'],[])

    def test_package_without_answers_omits_answer_only_images(self):
        from PIL import Image
        buf=BytesIO();Image.new('RGB',(20,20),'white').save(buf,'PNG');data=buf.getvalue();path='Assets/'+content.digest(data)+'.png';library.install_files(self.root,{path:data})
        id=self.op('create',subject_id=2,phase_id=2,text={'content':'独立题干','answer':'![只有答案里的图]('+path+')'})['id']
        r=self.op('package-export',ids=[id],include_solutions=False)
        with zipfile.ZipFile(self.root/r['url'].lstrip('/')) as z:self.assertEqual(z.namelist(),['manifest.json'])

    def test_local_search_descendants_tags_and_review_status(self):
        from types import SimpleNamespace
        self.tree();id=self.create();self.op('classify',ids=[id],hashes=self.hashes([id]),knowledge_tree_ids=['11'],tags=['重点'])
        args=SimpleNamespace(catalog='knowledge-2-2',node='10',archived=False,status='draft',tag='重点',type=None,unused=True,keyword='',limit=20)
        self.assertEqual(library.search(self.w.state(),args)['count'],1);self.review([id]);self.assertEqual(library.search(self.w.state(),args)['count'],0)

    def test_pdf_backup_restore_and_bad_batch_id_rejected(self):
        self.op('pdf-prepare',file_base64=base64.b64encode(pdf_fixture()).decode(),subject_id=2,phase_id=2)
        r=self.op('backup');data=self.archive_data(r);self.op('restore',file_base64=data,confirm=True)
        self.assertEqual(len(self.w.state()['pdf_batches'][0]['pages']),1)
        m,files=library.unpack_archive(base64.b64decode(data));m['state']['pdf_batches'][0]['id']='bad" onclick="alert(1)'
        out=BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            z.writestr('manifest.json',json.dumps(m))
            for name,bytes_ in files.items():z.writestr(name,bytes_)
        before=self.w.state()
        with self.assertRaises(StudioError):self.op('restore',file_base64=base64.b64encode(out.getvalue()).decode(),confirm=True)
        self.assertEqual(before,self.w.state())

    def test_reload_demo_does_not_replace_edits(self):
        self.op('demo');id=self.w.state()['questions'][0]['id'];self.op('edit',id=id,hashes=self.hashes([id]),text={'content':'老师的编辑内容','answer':'保留答案'});self.review([id]);before=self.q(id)
        self.op('demo');self.assertEqual(before,self.q(id))

if __name__=='__main__':unittest.main()
