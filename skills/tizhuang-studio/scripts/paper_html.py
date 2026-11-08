"""A4 browser preview and printing from the same grouped Word snapshot."""
import base64
import html
import re
from io import BytesIO
from lxml import html as dom
from PIL import Image
import content
from paper_layout import groups, needs_space


def body(root, question, value, prefix=''):
    node=dom.fragment_fromstring(content.render(value or '',question.get('content_format','html')),create_parent='div')
    # Common A-D option rows retain their MathML nodes in aligned columns.
    for paragraph in list(node.xpath('.//p|.//div')):
        if paragraph.xpath('./p|./div|.//table|.//img|.//mtext'):continue
        inner=html.escape(paragraph.text or '')+''.join(dom.tostring(c,encoding='unicode') for c in paragraph)
        parts=re.split(r'(?:^|[\s\u3000]+)([ABCD][.．、])\s*',inner)
        if len(parts)!=9 or parts[0].strip() or [p[0] for p in parts[1::2]]!=list('ABCD'):continue
        options=[dom.fragment_fromstring(parts[i]+' '+parts[i+1],create_parent='div') for i in range(1,9,2)]
        length=max(len(x.text_content().strip())-3 for x in options)
        columns=4 if length<=12 else 2 if length<=26 else 1
        paragraph.clear(keep_tail=True);paragraph.tag='div';paragraph.set('class',f'options cols-{columns}')
        for option in options:paragraph.append(option)
    assets={a['path']:a for a in question.get('assets',[])}
    for img in node.xpath('.//img'):
        source=img.get('src','');asset=assets.get(source)
        if not asset:raise ValueError('预览图片未登记在题目附件中。')
        data=content.asset_path(root,source).read_bytes()
        if content.digest(data)!=asset['sha256']:raise ValueError('预览图片校验失败。')
        with Image.open(BytesIO(data)) as picture:
            w,h=picture.size;default=144 if question.get('source',{}).get('provider')=='local-pdf' else 96
            dpi=picture.info.get('dpi',(default,default))[0]
            if not isinstance(dpi,(int,float)) or not 36<=dpi<=1200:dpi=default
            width=min(174,w*25.4/dpi,150*w/h)
        mime='image/jpeg' if source.endswith('.jpg') else 'image/'+source.rsplit('.',1)[-1]
        img.set('src','data:'+mime+';base64,'+base64.b64encode(data).decode())
        img.set('style',f'width:{width:g}mm;max-width:100%;height:auto;'+('display:block;margin:4pt auto;' if width*h/w>12 else ''))
    meaningful=bool(node.text_content().strip() or node.xpath('.//math|.//img'))
    if not meaningful:return ''
    if prefix:
        first=node
        while len(first) and first[0].tag in ('div','p') and not (first.text or '').strip():first=first[0]
        label=dom.Element('strong');label.text=prefix
        if len(first) and first[0].tag in ('table','img'):
            p=dom.Element('p');p.append(label);first.insert(0,p)
        else:
            label.tail=first.text;first.text=None;first.insert(0,label)
    return dom.tostring(node,encoding='unicode')


def render(root,manifest,teacher=False):
    sections=[]
    for group in groups(manifest):
        sections.append('<h2>'+html.escape(group['title'])+'</h2>')
        for item in group['items']:
            q=item['question'];stem=body(root,q,q['content'],f'{item["number"]}. （{item["score"]:g} 分）')
            text='<section class="question"><div class="stem">'+stem+'</div>'
            if teacher:
                answer=body(root,q,q.get('answer','')) or '<p>原题未提供答案</p>'
                analysis=body(root,q,q.get('analysis',''))
                text+='<h3>答案</h3>'+answer
                if analysis:text+='<h3>解析</h3>'+analysis
            elif needs_space(q):text+=f'<div class="answer-space" style="height:{float(manifest.get("answer_space_mm",20)):g}mm"></div>'
            sections.append(text+'</section>')
    duration=manifest.get('duration_minutes');total=sum(i['score'] for i in manifest['items'])
    meta=(f'考试时间：{duration:g} 分钟　　' if duration else '')+f'满分：{total:g} 分　　共 {len(manifest["items"])} 题'
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(manifest['title'])+'</title><style>'+CSS+'</style></head><body><main class="paper"><header><h1>'+html.escape(manifest['title'])+'</h1>'+('<p>教师答案版</p>' if teacher else '')+'<p>'+meta+'</p>'+('' if teacher else '<p class="identity">姓名：________________　　班级：________________</p>')+'</header>'+''.join(sections)+'</main></body></html>'


CSS='''
*{box-sizing:border-box}html{background:#ececec;color-scheme:light}body{margin:0;color:#000;font:11pt/1.2 "Times New Roman","SimSun","宋体",serif}.paper{width:210mm;min-height:297mm;margin:24px auto;padding:17mm 18mm;background:#fff;box-shadow:0 2px 15px #0002}header{text-align:center;margin-bottom:10pt}h1{font-size:20pt;font-weight:normal;margin:0 0 8pt}p{margin:0 0 5pt}header p{margin-bottom:5pt}.identity{margin-top:8pt}h2{font-size:12pt;margin:12pt 0 6pt;break-after:avoid}h3{font-size:11pt;margin:8pt 0 4pt;break-after:avoid}.question{margin:10pt 0 0;break-inside:avoid}.stem>div>p:first-child{margin-top:0}math{font-size:1em}table{border-collapse:collapse;max-width:100%;width:100%;margin:5pt 0}td,th{border:1px solid #d9d9d9;padding:3pt}th{background:#f2f2f2}img{max-width:100%}.answer-space{min-height:0}a{color:inherit;text-decoration:none}
.options{display:grid;gap:5pt 8pt;margin:4pt 0 5pt}.cols-4{grid-template-columns:repeat(4,minmax(0,1fr))}.cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}.cols-1{grid-template-columns:1fr}
@page{size:A4;margin:17mm 18mm;@bottom-center{content:"第 " counter(page) " 页";font-size:9pt}}
@media print{html{background:#fff}.paper{width:auto;min-height:0;margin:0;padding:0;box-shadow:none}body{print-color-adjust:exact}}
@media screen and (max-width:820px){.paper{width:100%;margin:0;min-height:100vh;padding:24px 20px}}
'''

