"""PDF -> editable drafts with original figures and traceable source regions."""
from pathlib import Path
import re
import math
import ui_layout as ui

SCHEMA = 'tizhuang.pdf-segmentation/v2'
LEGACY_SCHEMA = 'tizhuang.pdf-segmentation/v1'


def deps():
    try:
        import pdfplumber
        import pypdfium2
        from PIL import Image
        return pdfplumber, pypdfium2, Image
    except ImportError as exc:
        raise ValueError('PDF 依赖未安装，请在本地题库 Python 环境安装 scripts/requirements.txt') from exc


def batch_dir(bank, batch):
    if not re.fullmatch(r'[a-f0-9]{24}', batch):
        raise ValueError('无效的 PDF 导入批次编号')
    return bank.root / '.bank/imports' / batch


def report(bank, m):
    import local_bank as lb
    name = ui.name(m['filename']) + ' · ' + m['id'][:6]
    path = bank.root / '待整理' / (name + '.md')
    labels = {'prepared': '已定位候选，待 Agent 还原正文', 'needs_agent': '待 Agent 识别', 'imported': '已导入，待老师核对', 'partial': '部分导入，可继续'}
    text = f"# {m['filename']}\n\n状态：**{labels.get(m['status'], m['status'])}**\n\n共 {len(m['pages'])} 页 · 识别 {len(m.get('questions', []))} 题 · 已入库 {len(m.get('imported', {}))} 题\n\n"
    text += f"[查看原始 PDF](../{m['source_path']})\n\n"
    if m.get('warnings'):
        heading = '准备阶段记录（已完成分题）' if m['status'] == 'imported' else '需要留意'
        text += '## ' + heading + '\n\n' + '\n'.join('- ' + w for w in m['warnings']) + '\n\n'
    if m['status'] != 'imported':
        text += '## 在 Agent 中继续\n\n```text\n使用 tizhuang-local-bank，处理当前题库中的 PDF 导入批次 ' + m['id'] + '。查看全部原页，将题干、选项、公式和表格转为可编辑 Markdown/LaTeX，单独提取配图，去掉正文原题号及图片中的“第几题图”，原编号仅保留在来源记录。保留小问与图①等对应关系，核对原答案，根据考查内容关联到本地标准知识点树，综合题可关联多个知识点，不能只有标签；未指定教材不补章节。使用 v2 分题清单导入待核对题目。\n```\n\n'
    uncertainties = [(q['number'], s) for q in m.get('questions', []) for s in q.get('uncertainties', [])]
    if uncertainties:
        text += '## 识别待确认\n\n' + '\n'.join(f'- 来源第 {n} 题：{s}' for n, s in uncertainties) + '\n\n'
    if m.get('imported'):
        text += '## 已入库题目\n\n'
        bank.questions()
        for number, qid in m['imported'].items():
            path_q = bank.note_paths.get(qid)
            if path_q:
                text += f"- 第 {number} 题：[[{path_q.relative_to(bank.root).with_suffix('').as_posix()}]]\n"
    text += ('\n正文、公式与选项可编辑，配图保留原件像素；来源题号仅用于回查，组卷时重新编号。' if m.get('representation') == 'editable' else '\n原页与区域用于溯源；旧图片草稿可由 Agent 升级为可编辑题目。')
    text += '导入不会自动标为已核对，也不消耗网站题目额度。\n'
    lb.atomic(path, text)
    return path.relative_to(bank.root).as_posix()


def prepare(bank, args):
    import local_bank as lb
    pdfplumber, pdfium, _ = deps()
    source = Path(args.file).resolve()
    if source.suffix.lower() != '.pdf' or source.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('请选择不超过 100 MB 的 PDF 文件')
    data = source.read_bytes()
    if not data.startswith(b'%PDF-'):
        raise ValueError('文件不是有效 PDF')
    sha = lb.digest(data)
    batch = sha[:24]
    folder = batch_dir(bank, batch)
    manifest = folder / 'manifest.json'
    scope = {field: getattr(args, key, None) for key, field in [('subject', 'subject_id'), ('phase', 'phase_id'), ('edition', 'edition_id')]}
    scope['chapter_ids'] = list(map(str, getattr(args, 'chapter', None) or []))
    if scope['chapter_ids']:
        nodes = bank.chapters(scope['subject_id'], scope['phase_id'], scope['edition_id'])
        if any(n not in nodes for n in scope['chapter_ids']):
            raise ValueError('指定章节不属于所选教材')
    if manifest.exists():
        previous = lb.read_json(manifest)
        if previous['scope'] != scope:
            raise ValueError('这份 PDF 已有其他学科或教材范围的导入记录，请先核对原批次，避免重复归类')
        if previous.get('status'):
            return summary(bank, previous, reused=True)
    source_rel = f'资料/原件/{sha}.pdf'
    lb.atomic(bank.root / source_rel, data)
    m = {'schema': 'tizhuang.pdf-import/v1', 'id': batch, 'filename': source.name, 'sha256': sha, 'source_path': source_rel, 'scope': scope, 'pages': [], 'questions': [], 'imported': {}, 'warnings': [], 'created_at': lb.now(), 'status': 'needs_agent'}
    events = []
    mode = 'content'
    doc = pdfium.PdfDocument(data)
    try:
        if not 1 <= len(doc) <= 120:
            raise ValueError('第一版每个导入批次支持 1–120 页，请按试卷拆分文件')
        with pdfplumber.open(source) as pdf:
            for index, page in enumerate(pdf.pages):
                if page.width * page.height > 4_000_000:
                    raise ValueError('页面尺寸过大，请先将工程图或长图转换为普通试卷页面')
                image_path = folder / f'pages/{index+1:03}.png'
                image_path.parent.mkdir(parents=True, exist_ok=True)
                pdfpage = doc[index]
                bitmap = pdfpage.render(scale=2)
                bitmap.to_pil().save(image_path)
                bitmap.close()
                pdfpage.close()
                text = page.extract_text() or ''
                lines = page.extract_text_lines()
                page_meta = {'number': index+1, 'width': float(page.width), 'height': float(page.height), 'image': f'pages/{index+1:03}.png', 'text': f'pages/{index+1:03}.txt', 'characters': len(text.strip()), 'lines': [{k: line[k] for k in ('text', 'x0', 'x1', 'top', 'bottom')} for line in lines]}
                m['pages'].append(page_meta)
                lb.atomic(folder / page_meta['text'], text)
                if len(text.strip()) < 15:
                    m['warnings'].append(f'第 {index+1} 页没有足够文字，需要 Agent 查看原页识别；不会把整页当成一道题。')
                for line in lines:
                    value = line['text'].strip()
                    if len(re.findall(r'(?:^|\s)[1-9]\d{0,2}[.．、](?!\d)', value)) > 1:
                        m['warnings'].append('同一行出现多个题号，可能为双栏或紧排答案；需要 Agent 确认区域。')
                    if re.match(r'^(?:参考答案|答案与解析|参考答案及解析|答案解析)\s*[:：]?$', value):
                        mode = 'answer'
                        events.append({'kind': 'boundary', 'page': index+1, 'y': max(0, line['top']-3)})
                        continue
                    match = re.match(r'^(?:第\s*(\d{1,3})\s*题(?=$|\s|[:：.．、])|([1-9]\d{0,2})[．、.]\s*)(?!\d)', value)
                    if match:
                        events.append({'kind': mode, 'number': match[1] or match[2], 'page': index+1, 'y': max(0, float(line['top'])-4), 'x': float(line['x0']), 'text': value})
    finally:
        doc.close()
    numbered = [e for e in events if e['kind'] != 'boundary']
    if any(e['x'] > m['pages'][e['page']-1]['width'] * .38 for e in numbered):
        m['warnings'].append('发现右侧题号，可能为双栏排版；需要 Agent 按列划分原页区域。')
    content = [e for e in numbered if e['kind'] == 'content']
    for kind in ('content', 'answer'):
        nums = [int(e['number']) for e in numbered if e['kind'] == kind]
        if nums and (len(nums) != len(set(nums)) or nums != list(range(nums[0], nums[0] + len(nums)))):
            m['warnings'].append('题号不连续或重复，需要核对是否有章节重编号、子题或跨栏。')
    if not content:
        m['warnings'].append('没有识别到可靠题号，需要 Agent 在原页上标出题目区域。')
    def regions(start, stop):
        end_page = stop['page'] if stop else len(m['pages'])
        result = []
        for num in range(start['page'], end_page+1):
            p = m['pages'][num-1]
            top = start['y'] if num == start['page'] else 12
            bottom = stop['y'] if stop and num == end_page else p['height']-12
            if bottom-top >= 5:
                result.append({'page': num, 'bbox': [12, top, p['width']-12, bottom]})
        return result
    questions = {}
    for idx, e in enumerate(events):
        if e['kind'] == 'boundary':
            continue
        q = questions.setdefault(e['number'], {'number': e['number'], 'title': ui.clean_title(e['text']), 'content_regions': [], 'answer_regions': [], 'tags': ['PDF导入'], 'type': '未分类'})
        q[e['kind'] + '_regions'] += regions(e, events[idx+1] if idx+1 < len(events) else None)
        if e['kind'] == 'content':
            q['title'] = ui.clean_title(e['text'])
    m['questions'] = [q for q in questions.values() if q['content_regions']]
    m['status'] = 'needs_agent' if m['warnings'] else 'prepared'
    lb.atomic(manifest, lb.json_text(m))
    lb.atomic(folder / 'segmentation.json', lb.json_text({'schema': LEGACY_SCHEMA, 'questions': m['questions']}))
    return summary(bank, m)


def summary(bank, m, **extra):
    path = report(bank, m)
    return {'batch': m['id'], 'status': m['status'], 'pages': len(m['pages']), 'questions': len(m['questions']), 'imported': len(m['imported']), 'warnings': m['warnings'], 'report': path, 'manifest': str(batch_dir(bank, m['id']) / 'manifest.json'), **extra}


def validate_segments(m, questions):
    if not isinstance(questions, list) or not 1 <= len(questions) <= 500:
        raise ValueError('分题清单必须包含 1–500 道题')
    seen = set()
    for q in questions:
        number = str(q.get('number', ''))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,30}', number) or number in seen:
            raise ValueError('原题编号为空、重复或无效；重编号时包含章节前缀')
        seen.add(number)
        if not q.get('content_regions'):
            raise ValueError(f'第 {number} 题缺少原页区域')
        for key in ('content_regions', 'answer_regions', 'analysis_regions', 'figures'):
            for region in q.get(key, []):
                page = region.get('page')
                if not isinstance(page, int) or not 1 <= page <= len(m['pages']):
                    raise ValueError('原页页码无效')
                box = region.get('bbox')
                size = m['pages'][page-1]
                if not isinstance(box, list) or len(box) != 4 or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in box):
                    raise ValueError('原页区域必须是四个有限坐标')
                if not (0 <= box[0] < box[2] <= size['width'] and 0 <= box[1] < box[3] <= size['height']):
                    raise ValueError('原页裁切区域超出边界')


def validate_editable(questions):
    """Reject image-only bodies and ambiguous figure references before any bank writes."""
    for item in questions:
        number = str(item['number'])
        content = item.get('content_markdown', '')
        if not isinstance(content, str) or not re.search(r'[\w\u4e00-\u9fff]', re.sub(r'\{\{figure:[^}]+\}\}|!\[[^]]*\]\([^)]*\)', '', content)):
            raise ValueError(f'第 {number} 题缺少可编辑题干，不能以整题图片代替')
        if re.match(rf'^\s*(?:第\s*{re.escape(number)}\s*题|{re.escape(number)}[.．、](?!\d))', content):
            raise ValueError(f'第 {number} 题正文仍带原卷题号，请移到来源记录')
        figures = item.get('figures', [])
        ids = [f.get('id', '') for f in figures]
        if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', s) for s in ids):
            raise ValueError('配图 ID 重复或无效')
        text = '\n'.join(item.get(k + '_markdown', '') for k in ('content', 'answer', 'analysis'))
        used = re.findall(r'\{\{figure:([A-Za-z0-9_-]+)\}\}', text)
        if set(used) != set(ids) or '{{figure:' in re.sub(r'\{\{figure:[A-Za-z0-9_-]+\}\}', '', text):
            raise ValueError('配图占位符与 figures 清单不一致')
        if re.search(r'!\[|<img\b', text, re.I):
            raise ValueError('PDF 配图请使用 figure 占位符，由工具提取并校验')
        if not isinstance(item.get('uncertainties', []), list) or any(not isinstance(s, str) for s in item.get('uncertainties', [])):
            raise ValueError('识别疑点必须是文字列表')


def upgrade_editable(bank, pending, folder):
    """Explicit, backed-up v1 -> v2 upgrade; never overwrite teacher body edits."""
    import local_bank as lb
    import os
    import uuid
    import zipfile
    existing = {q['id']: q for q in bank.questions()}
    changes = []
    assets = {}
    for proposed in pending:
        q = dict(proposed)
        for asset in q['assets']:
            data = lb.inside(folder, lb.safe_relative(asset['path'])).read_bytes()
            sha = lb.digest(data)
            if sha != asset['sha256']:
                raise ValueError('配图 SHA256 不一致')
            new = f'Assets/{sha}.png'
            assets[bank.root / ui.asset_dir(bank.root) / f'{sha}.png'] = data
            for key in ('content', 'answer', 'analysis'):
                q[key] = q[key].replace(asset['path'], new)
        q['assets'] = [{'path': 'Assets/' + p.name, 'sha256': lb.digest(data)} for p, data in assets.items() if ('Assets/' + p.name) in '\n'.join(q[k] for k in ('content','answer','analysis'))]
        old = existing.get(q['id'])
        if old is None:
            raise ValueError('升级只处理同批次已入库题目；缺少题目：' + q['id'])
        record_path = bank.root / '.bank/records' / (q['id'] + '.json')
        record = lb.read_json(record_path)
        if old['source'] != q['source'] or record.get('original_payload', {}).get('pdf_sha256') != q['original_payload']['pdf_sha256']:
            raise ValueError('升级题目来源不一致')
        if all(old[k] == q[k] for k in ('content','answer','analysis')):
            continue
        if old['status'] != 'draft':
            raise ValueError('已核对题目不可自动升级：' + q['id'])
        if any(old[k] != record[k] for k in ('content','answer','analysis')):
            raise ValueError('老师已修改正文、答案或解析，停止覆盖：' + q['id'])
        if record.get('original_payload', {}).get('representation') == 'editable':
            raise ValueError('已有可编辑版本不同，请人工核对版本：' + q['id'])
        # Keep the original note path, YAML and all text outside the managed sections.
        path = bank.note_paths[q['id']]
        before = path.read_bytes()
        text = before.decode('utf-8-sig')
        prefix = os.path.relpath(bank.root / ui.asset_dir(bank.root), path.parent).replace('\\', '/') + '/'
        for key in ('content','answer','analysis'):
            value = q[key].replace('Assets/', prefix)
            text = re.sub(rf'(<!-- bank:{key}:start -->\r?\n).*?(\r?\n<!-- bank:{key}:end -->)', lambda match: match[1] + value + match[2], text, flags=re.S)
        merged = {**record, **old, **{k:q[k] for k in ('content','answer','analysis','assets','original_payload')}}
        changes.extend([(path, before, text.encode('utf-8')), (record_path, record_path.read_bytes(), lb.json_text(merged).encode('utf-8'))])
    if not changes:
        return None
    backup = folder / 'backups' / ('editable-' + uuid.uuid4().hex[:12] + '.zip')
    backup.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(backup, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(folder / 'manifest.json', 'manifest.json')
        for path, before, _ in changes:
            z.writestr(path.relative_to(bank.root).as_posix(), before)
    # Attachments are content addressed; retain old ones for old papers and rollback.
    for path, data in assets.items():
        if not path.exists():
            lb.atomic(path, data)
    written = []
    try:
        for path, before, after in changes:
            if path.read_bytes() != before:
                raise ValueError('题目正在被其他程序修改，停止升级')
            lb.atomic(path, after)
            written.append((path, before, after))
    except Exception:
        for path, before, after in reversed(written):
            if path.read_bytes() == after:
                lb.atomic(path, before)
        raise
    return str(backup)


def commit(bank, args):
    import local_bank as lb
    _, _, Image = deps()
    from PIL import ImageChops
    folder = batch_dir(bank, args.batch)
    m = lb.read_json(folder / 'manifest.json')
    if lb.digest((bank.root / m['source_path']).read_bytes()) != m['sha256']:
        raise ValueError('原始 PDF 已改变，停止导入')
    if args.segmentation:
        payload = lb.read_json(args.segmentation)
        schema = payload.get('schema')
        if schema not in (SCHEMA, LEGACY_SCHEMA):
            raise ValueError('不支持的分题协议')
        questions = payload.get('questions')
    else:
        if m['status'] == 'needs_agent':
            raise ValueError('本批次需要 Agent 查看原页并提供 --segmentation，不能直接自动入库')
        questions = m['questions']
        schema = m.get('segmentation_schema', LEGACY_SCHEMA)
    validate_segments(m, questions)
    editable = schema == SCHEMA
    if editable:
        validate_editable(questions)
    elif not getattr(args, 'image_draft', False):
        raise ValueError('请由 Agent 提供 v2 可编辑分题清单；仅明确需要图片草稿时使用 --image-draft')
    if getattr(args, 'upgrade_to_editable', False) and not editable:
        raise ValueError('升级需要 v2 可编辑分题清单')
    pending = []
    for item in questions:
        q = {'schema': lb.SCHEMA, 'id': 'pdf-' + m['id'] + '-' + str(item['number']), 'title': ui.clean_title(item.get('title') or 'PDF 第' + str(item['number']) + '题'), **m['scope'], 'knowledge_tree_ids': item.get('knowledge_tree_ids', []), 'knowledge_ids': [], 'tags': ui.native_tags(['PDF导入', *item.get('tags', [])]), 'type': item.get('type') or '未分类', 'difficulty': item.get('difficulty'), 'status': 'draft', 'score': item.get('score', 5), 'assets': [], 'source': {'kind': 'pdf', 'provider': 'local-pdf', 'external_id': m['sha256'] + ':' + str(item['number']), 'label': m['filename'] + ' · 第' + str(item['number']) + '题'}, 'search_text': item.get('search_text', ''), 'original_payload': {'pdf_sha256': m['sha256'], 'source_path': m['source_path'], 'segmentation': item}}
        q['original_payload']['representation'] = 'editable' if editable else 'image-draft'
        keys = ('figures',) if editable else ('content', 'answer', 'analysis')
        for key in keys:
            parts = []
            for i, region in enumerate(item.get(key if editable else key + '_regions', [])):
                p = m['pages'][region['page']-1]
                with Image.open(folder / p['image']) as image:
                    box = region['bbox']
                    sx, sy = image.width / p['width'], image.height / p['height']
                    crop = image.crop((math.floor(box[0]*sx), math.floor(box[1]*sy), math.ceil(box[2]*sx), math.ceil(box[3]*sy)))
                    # Remove only empty outer margins; diagrams and original pixels keep their colours.
                    rgb = crop.convert('RGB')
                    ink = ImageChops.difference(rgb, Image.new('RGB', rgb.size, 'white')).getbbox()
                    if ink:
                        crop = crop.crop((max(0,ink[0]-6),max(0,ink[1]-6),min(crop.width,ink[2]+6),min(crop.height,ink[3]+6)))
                    file = folder / f"crops/{item['number']}-{key}-{i}.png"
                    file.parent.mkdir(parents=True, exist_ok=True)
                    crop.save(file)
                rel = file.relative_to(folder).as_posix()
                q['assets'].append({'path': rel, 'sha256': lb.digest(file.read_bytes())})
                parts.append(f"![原题第{item['number']}题·第{region['page']}页]({rel})")
                if key == 'content' and not item.get('search_text'):
                    q['search_text'] += '\n' + '\n'.join(line['text'] for line in p.get('lines', []) if box[1] <= (line['top']+line['bottom'])/2 <= box[3] and box[0] <= (line['x0']+line['x1'])/2 <= box[2])
            q[key] = '\n\n'.join(parts)
        if editable:
            for key in ('content', 'answer', 'analysis'):
                q[key] = item.get(key + '_markdown', '')
                for i, figure in enumerate(item.get('figures', [])):
                    q[key] = q[key].replace('{{figure:' + figure['id'] + '}}', f"![配图](crops/{item['number']}-figures-{i}.png)")
            q.pop('figures', None)
            q['search_text'] = item.get('search_text') or q['content']
        q = lb.normalize(q)
        if q['knowledge_tree_ids']:
            tree = bank.taxonomy(q.get('subject_id'), q.get('phase_id'))
            if any(n not in tree for n in q['knowledge_tree_ids']):
                raise ValueError('PDF 分题清单含无效知识节点')
            # Exact IDs are supplied by the local tree, never assumed equal to tree-node IDs.
            q['knowledge_ids'] = list(dict.fromkeys(str(tree[n]['knowledge_id']) for n in q['knowledge_tree_ids'] if tree[n].get('knowledge_id') is not None))
            q['tags'] = ui.native_tags([*q['tags'], *['考点/' + tree[n]['name'] for n in q['knowledge_tree_ids']]])
        pending.append(q)
    if editable and not getattr(args, 'upgrade_to_editable', False):
        existing = {q['id']: q for q in bank.questions()}
        for q in pending:
            old = existing.get(q['id'])
            if old:
                for key in ('content', 'answer', 'analysis'):
                    canonical = q[key]
                    for asset in q['assets']:
                        canonical = canonical.replace(asset['path'], 'Assets/' + asset['sha256'] + '.png')
                    if canonical != old[key]:
                        raise ValueError('已有同 ID 题目的正文、答案或解析不同，停止覆盖；图片草稿升级请显式使用 --upgrade-to-editable')
    if getattr(args, 'upgrade_to_editable', False):
        backup = upgrade_editable(bank, pending, folder)
        m['upgrade_backup'] = backup or m.get('upgrade_backup')
    m['questions'] = questions
    m['segmentation_schema'] = schema
    m['representation'] = 'editable' if editable else 'image-draft'
    m['status'] = 'partial'
    lb.atomic(folder / 'manifest.json', lb.json_text(m))
    for q in pending:
        result = {'id': q['id']} if getattr(args, 'upgrade_to_editable', False) else bank.save(q, folder)
        number = q['original_payload']['segmentation']['number']
        m['imported'][str(number)] = result['id']
        lb.atomic(folder / 'manifest.json', lb.json_text(m))
    m['status'] = 'imported'
    lb.atomic(folder / 'manifest.json', lb.json_text(m))
    result = summary(bank, m)
    from auto_classify import run as auto_classify
    from types import SimpleNamespace
    try:
        result['classification'] = auto_classify(bank, SimpleNamespace(batch=m['id']))
    except Exception as error:
        # The questions are saved; report a recoverable classification problem accurately.
        result['classification'] = {'error': str(error), 'pending': len(pending)}
    bank.questions()
    return result
