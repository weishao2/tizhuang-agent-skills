"""PDF preparation and reviewed, editable segmentation. Coordinates are top-left PDF points."""
import copy,hashlib,json,math,re,shutil,uuid
from io import BytesIO
from pathlib import Path
import content,library

SCHEMA='tizhuang.pdf-segmentation/v2'

def region(raw,pages):
    if not isinstance(raw,dict) or type(raw.get('page')) is not int or not 1<=raw['page']<=len(pages):raise ValueError('PDF 页码无效。')
    page=pages[raw['page']-1];box=raw.get('bbox')
    if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box):raise ValueError('区域须为 [左, 上, 右, 下] PDF 点坐标。')
    x0,y0,x1,y1=box
    if not 0<=x0<x1<=page['width'] or not 0<=y0<y1<=page['height']:raise ValueError('PDF 区域超出原页。')
    return {'page':raw['page'],'bbox':box}

def apply(w,b,s,questions):
    if b['action']=='pdf-prepare':return prepare(w,b,s)
    batch=next((v for v in s['pdf_batches'] if v['id']==b.get('batch_id')),None)
    if not batch:raise ValueError('PDF 批次不存在，请先上传原文件。')
    plan=b.get('plan',{});rows=plan.get('questions')
    if plan.get('schema')!=SCHEMA or not isinstance(rows,list) or not 1<=len(rows)<=200:raise ValueError('请提供 v2 可编辑分题清单，1–200 道题。')
    folder=w.root/'pdf'/batch['id'];pending=[];files={};numbers=set();skipped=[]
    from engine import prepare as freeze
    from PIL import Image
    for raw in rows:
        num=str(raw.get('number','')).strip()
        if not num or len(num)>30 or num in numbers:raise ValueError('原题号为空、过长或重复。')
        numbers.add(num);ident='pdf-'+batch['id']+'-'+hashlib.sha256(num.encode()).hexdigest()[:10]
        digest=content.digest(json.dumps(raw,sort_keys=True,ensure_ascii=False).encode())
        if ident in questions:
            if questions[ident].get('source_pdf',{}).get('segmentation_hash')!=digest:raise ValueError('这道题已入库且分题内容不同；请在题目编辑中修改，避免覆盖老师的核对。')
            skipped.append(ident);continue
        sections={key:raw.get(key+'_markdown','') for key in ['content','answer','analysis']}
        if any(not isinstance(v,str) or len(v)>500000 for v in sections.values()):raise ValueError('分题正文须为 Markdown 文本。')
        if any(re.search(r'!\[[^\]]*\]\(|<img',v,re.I) for v in sections.values()):raise ValueError('请用 {{figure:编号}} 引用原页裁图，不要插入外部图片或整题截图。')
        # Strip only the outer original number; retain subquestion and option numbers.
        sections['content']=re.sub(r'^\s*'+re.escape(num)+r'\s*[.．、)）]\s*','',sections['content'],count=1)
        readable=re.sub(r'\{\{figure:[^}]+\}\}|!\[[^\]]*\]\([^)]*\)|<[^>]+>','',sections['content']).strip()
        if not readable:raise ValueError('需要可编辑题干，不能以整题截图代替正文。')
        refs={key:[region(r,batch['pages']) for r in raw.get(key+'_regions',[])] for key in sections}
        if not refs['content']:raise ValueError('每题至少保留一个题干原页区域，供核对。')
        figids=set();assets=[]
        for f in raw.get('figures',[]):
            fid=f.get('id','')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',fid) or fid in figids:raise ValueError('配图编号无效或重复。')
            figids.add(fid);r=region(f,batch['pages']);pg=batch['pages'][r['page']-1];x0,y0,x1,y1=r['bbox']
            if (x1-x0)*(y1-y0)>pg['width']*pg['height']*.75:raise ValueError('配图区域过大，请只裁真实图形，不要裁整页或整道题。')
            with Image.open(folder/pg['image']) as img:
                sx,sy=img.width/pg['width'],img.height/pg['height'];cropped=img.crop((round(x0*sx),round(y0*sy),round(x1*sx),round(y1*sy)))
                output=BytesIO();cropped.save(output,'PNG');data=output.getvalue()
            path='Assets/'+content.digest(data)+'.png';files[path]=data;assets.append({'path':path,'sha256':content.digest(data)})
            token='{{figure:'+fid+'}}'
            if not any(token in v for v in sections.values()):raise ValueError('配图没有被题干、答案或解析引用。')
            for key in sections:sections[key]=sections[key].replace(token,'![配图]('+path+')')
        if any('{{figure:' in v for v in sections.values()):raise ValueError('正文引用了不存在的配图。')
        if any(re.search(r'!\[|<img',v) for v in sections.values()) and not assets:raise ValueError('配图必须由原页区域生成。')
        q=library.decorate({'id':ident,**{k:content.render(v) for k,v in sections.items()},'editable':{**sections,'format':'markdown'},'subject_id':batch['subject_id'],'phase_id':batch['phase_id'],'type':str(raw.get('type','解答题'))[:40],
          'difficulty':raw.get('difficulty'),'knowledge':str(raw.get('knowledge','')),'tags':library.strings(raw.get('tags',[])),
          'knowledge_tree_ids':[str(i) for i in raw.get('knowledge_tree_ids',[])],'chapter_ids':[str(i) for i in raw.get('chapter_ids',[])],'edition_id':raw.get('edition_id'),
          'assets':assets,'source':{'label':batch['filename'],'external_id':num},'status':'draft','created_at':library.stamp(),
          'source_pdf':{'batch_id':batch['id'],'number':num,'segmentation_hash':digest,**refs,'figures':raw.get('figures',[]),'uncertainties':library.strings(raw.get('uncertainties',[]))}})
        library.validate_links(q,s['catalogs'])
        # No arbitrary URLs/files in segmentation: only this question's cropped assets.
        from lxml import html
        for key in sections:
            for src in html.fragment_fromstring(q[key] or '<span></span>',create_parent='div').xpath('.//img/@src'):
                if src not in {a['path'] for a in assets}:raise ValueError('PDF 题目引用了非本题的图片。')
        pending.append(q)
    library.install_files(w.root,files)
    pending=[freeze(q,w.root) for q in pending]
    # Classify only exact unique labels, never invent a textbook or node.
    classified,_=library.apply(w,{'action':'auto-classify','ids':[q['id'] for q in pending]},copy.deepcopy(s),{q['id']:q for q in pending}) if pending else ([],{})
    enriched={q['id']:q for q in classified};pending=[enriched.get(q['id'],q) for q in pending]
    batch['question_ids']=list(dict.fromkeys(batch.get('question_ids',[])+[q['id'] for q in pending]+skipped));batch['status']='imported';batch['updated_at']=library.stamp()
    (folder/'manifest.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/('segmentation-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    return pending,{'imported_ids':[q['id'] for q in pending],'existing_ids':skipped,'batch_id':batch['id'],'message':'已保存为待核对题目；未识别的知识点可交给 Agent 分类。'}

def prepare(w,b,s):
    import pypdfium2 as pdfium
    data=library.filedata(b,30*1024*1024)
    if not data.startswith(b'%PDF-'):raise ValueError('文件不是有效 PDF。')
    scope={k:library.identity(b.get(k)) for k in ['subject_id','phase_id']}
    ident=content.digest(data)[:24];existing=next((x for x in s['pdf_batches'] if x['id']==ident),None)
    if existing:
        if any(existing[k]!=scope[k] for k in scope):raise ValueError('同一 PDF 已用其他学科学段导入，请复用并核对原批次。')
        return [],{'batch_id':ident,'existing':True}
    target=w.root/'pdf'/ident;staging=w.root/'pdf'/('pending-'+uuid.uuid4().hex);staging.mkdir(parents=True)
    try:
        with pdfium.PdfDocument(data) as doc:
            if not 1<=len(doc)<=60:raise ValueError('每批 PDF 支持 1–60 页，请先拆分较长文件。')
            batch={'id':ident,**scope,'filename':str(b.get('filename','试卷.pdf')).replace('\\','/').split('/')[-1][:120],'pages':[],'question_ids':[],'status':'prepared','created_at':library.stamp()}
            total_pixels=0
            for n in range(len(doc)):
                page=doc[n]
                try:
                    width,height=page.get_size();total_pixels+=width*height*4
                    if width*height*4>16000000 or total_pixels>200000000:raise ValueError('PDF 页面尺寸或渲染规模过大，请拆分后重试。')
                    tp=page.get_textpage()
                    try:text=tp.get_text_range()
                    finally:tp.close()
                    image=f'page-{n+1}.png';bitmap=page.render(scale=2)
                    try:bitmap.to_pil().save(staging/image)
                    finally:bitmap.close()
                    (staging/f'page-{n+1}.txt').write_text(text,encoding='utf-8')
                    batch['pages'].append({'number':n+1,'width':width,'height':height,'image':image,'text':text,'needs_visual_reading':not text.strip()})
                finally:page.close()
        (staging/'original.pdf').write_bytes(data);(staging/'manifest.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2),encoding='utf-8')
        # A prior interrupted prepare may have left an unreferenced batch. Preserve it.
        if target.exists():
            if (target/'original.pdf').read_bytes()!=data:raise ValueError('批次文件冲突，请检查工作台。')
        else:staging.rename(target)
        s['pdf_batches'].insert(0,batch)
        return [],{'batch_id':ident,'pages':len(batch['pages']),'message':'原页已准备好；请让 Agent 查看原页并提交可编辑分题清单。'}
    finally:
        if staging.exists() and (w.root/'pdf').resolve() in staging.resolve().parents:shutil.rmtree(staging)
