"""Shared local basket/CLI paper generation. Snapshots never change bank scores."""
from pathlib import Path
import copy
import datetime as dt
import html
import json
import math
import re
import uuid
import yaml
import ui_layout as ui


def number(value, field, lower, upper, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper or (integer and int(value) != value):
        raise ValueError(f'{field}必须为 {lower}—{upper} 范围内的有效数字')
    return value


def load_basket(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data.get('schema') != 'tizhuang.paper-basket/v1':
        raise ValueError('不支持的组卷篮格式')
    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 200:
        raise ValueError('组卷篮需要 1—200 道题')
    ids = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('question_id'), str):
            raise ValueError('组卷篮缺少题目 ID')
        ids.append(item['question_id'])
        number(item.get('score'), '每题分值', 0, 1000)
    if len(ids) != len(set(ids)):
        raise ValueError('组卷篮含重复题目')
    if not isinstance(data.get('title'), str) or not data['title'].strip() or len(data['title']) > 120:
        raise ValueError('请填写 1—120 字的试卷标题')
    number(data.get('duration_minutes', 45), '考试时长', 1, 600, True)
    number(data.get('answer_space_mm', 25), '作答留白', 0, 100, True)
    if data.get('request_id') and not re.fullmatch(r'[a-f0-9]{32}', data['request_id']):
        raise ValueError('无效的生成请求编号')
    return data


def outputs(out, manifest, reused=False):
    return {'paper_id': manifest['id'], 'questions': len(manifest['items']), 'score': manifest['total_score'], 'student': str(out / '打印稿/试卷.html'), 'teacher': str(out / '教师稿/试卷.html'), 'note': str(out / '试卷.md'), 'manifest': str(out / 'manifest.json'), 'reused': reused, **({key: str(out / rel) for key, rel in [('student_docx', '打印稿/试卷.docx'), ('teacher_docx', '教师稿/试卷.docx')]} if manifest.get('docx_version') == 1 else {})}


def build(bank, args):
    import local_bank as lb
    basket_path = getattr(args, 'basket', None)
    basket = load_basket(basket_path) if basket_path else None
    request_hash = lb.digest(lb.json_text(basket).encode()) if basket else None
    request_id = basket.get('request_id') if basket else None
    title = basket['title'].strip() if basket else getattr(args, 'title', '本地练习卷')
    paper_id = request_id or (dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    final_out = bank.root / ui.PAPER_DIR / (ui.name(title) + ' · ' + paper_id)
    # A response may be lost after successful publication; retry the same frozen request.
    prior = list((bank.root / ui.PAPER_DIR).glob('* · ' + request_id)) if request_id else []
    if prior and not args.plan:
        final_out = prior[0]
        manifest = lb.read_json(final_out / 'manifest.json')
        if manifest.get('request_hash') != request_hash:
            raise ValueError('同一生成请求的内容已改变，请重新生成')
        for rel, expected in manifest.get('output_hashes', {}).items():
            if lb.digest(lb.inside(final_out, rel).read_bytes()) != expected:
                raise ValueError('已生成的试卷文件发生变化，请保留原件并重新生成')
        if not manifest.get('output_hashes'):
            raise ValueError('试卷输出校验信息缺失')
        return outputs(final_out, manifest, True)
    if basket:
        if args.ids or args.count is not None or any(getattr(args, k, None) for k in ('subject', 'phase', 'grade', 'edition', 'chapter', 'type', 'tag', 'knowledge', 'query', 'unused')):
            raise ValueError('组卷篮已包含明确题序，不能再叠加选题参数')
        chosen = lb.get_ids(bank, [i['question_id'] for i in basket['items']])
        available = len(chosen)
    else:
        chosen = lb.get_ids(bank, args.ids) if args.ids else bank.select(args)
        if args.ids:
            allowed = {q['id'] for q in bank.select(args)}
            if any(q['id'] not in allowed for q in chosen) and all(q['status'] == 'reviewed' for q in chosen):
                raise ValueError('指定题目不符合筛选条件，不能忽略条件组卷')
        required = getattr(args, 'count', None) if getattr(args, 'count', None) is not None else len(chosen)
        if required <= 0 or len(chosen) < required:
            raise ValueError(f'题目不足: 需要 {required}，筛选后只有 {len(chosen)}；不会放宽条件')
        available = len(chosen)
        chosen = chosen[:required]
    draft = [q for q in chosen if q['status'] != 'reviewed']
    confirmed = bool(basket and getattr(args, 'confirm_reviewed', False))
    if draft and not confirmed:
        raise ValueError('正式组卷只允许 reviewed 题目，请先核对题干、答案、附件再 review；插件可勾选已逐题核对后生成')
    originals = {q['id']: bank.note_paths[q['id']].read_bytes() for q in chosen}
    for q in chosen:
        lb.verify_media(bank, q)
    scores = [i['score'] for i in basket['items']] if basket else [q['score'] for q in chosen]
    if args.plan:
        return {'available': available, 'required': len(chosen), 'ids': [q['id'] for q in chosen], 'score': round(sum(scores), 2)}
    chosen = copy.deepcopy(chosen)
    # Reviewed confirmation applies only to the exact records read for this build.
    for q in chosen:
        if confirmed:
            q['status'] = 'reviewed'
    duration = basket.get('duration_minutes', 45) if basket else getattr(args, 'duration', None)
    if duration is not None:
        number(duration, '考试时长', 1, 600, True)
    space = basket.get('answer_space_mm', 25) if basket else 25
    items = [{'number': n, 'score': score, 'question': q} for n, (q, score) in enumerate(zip(chosen, scores), 1)]
    manifest = {'schema': 'tizhuang.paper/v1', 'id': paper_id, 'title': title, 'created_at': lb.now(), 'items': items, 'total_score': round(sum(scores), 2), 'duration_minutes': duration, 'request_hash': request_hash, 'basket': basket, 'docx_version': 1}
    # Never reuse partial assets from an interrupted build whose source notes changed.
    out = bank.root / '.bank/staging' / (paper_id + '-' + uuid.uuid4().hex[:8])
    css = (Path(__file__).parent / 'paper-print.css').read_text(encoding='utf-8')
    def render_section(item, field, label):
        question = item['question']
        try:
            return lb.render(question[field].replace('Assets/', '附件/'), question['content_format'])
        except ValueError as exc:
            raise ValueError(f'第 {item["number"]} 题 · {label}：{exc}') from exc

    for teacher in (False, True):
        role = '教师稿' if teacher else '打印稿'
        description = '教师答案版' if teacher else '无答案试卷'
        body = f'<header class="paper-sheet-head"><small>题庄 · 本地题库　{description}</small><h1>{html.escape(title)}</h1><p>'
        body += (f'考试时间：{duration} 分钟　　' if duration else '') + f'满分：{manifest["total_score"]:g} 分　　共 {len(items)} 题</p>'
        if not teacher:
            body += '<p class="paper-candidate-meta">姓名：________________　班级：________________</p>'
        body += '</header>'
        assets = {}
        for item in items:
            q = item['question']
            visible = q['content'] + (q['answer'] + q['analysis'] if teacher else '')
            for asset in q['assets']:
                if asset['path'] in visible:
                    data = ui.asset_path(bank.root, asset['path']).read_bytes()
                    if lb.digest(data) != asset['sha256']:
                        raise ValueError('组卷附件发生改变')
                    assets[asset['path'].replace('Assets/', '附件/')] = data
            body += f'<article class="paper-item"><h3>{item["number"]}. <span>（{item["score"]:g} 分）</span></h3><div class="question-content">' + render_section(item, 'content', '题干') + '</div>'
            if teacher:
                body += '<section class="paper-solution"><h4>答案</h4>' + (render_section(item, 'answer', '答案') if q['answer'].strip() else '<p class="missing-answer">原题未提供答案</p>')
                if q['analysis'].strip():
                    body += '<h4>解析</h4>' + render_section(item, 'analysis', '解析')
                body += '</section>'
            elif space:
                body += f'<div class="answer-space" style="height:{space}mm"></div>'
            body += '</article>'
        for rel, data in assets.items():
            lb.atomic(out / role / rel, data)
        toolbar = '<aside class="print-toolbar"><span>' + description + '</span><button onclick="window.print()">打印 / 保存为 PDF</button></aside>'
        document = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + ' · ' + description + '</title><style>' + css + '</style></head><body>' + toolbar + '<main class="paper-sheet">' + body + '</main></body></html>'
        lb.atomic(out / role / '试卷.html', document)
        try:
            from docx_export import export_docx
        except ImportError as exc:
            raise ValueError('Word 导出依赖未安装，请在插件使用的 Python 中安装 helper/requirements.txt') from exc
        export_docx(bank, manifest, out / role / '试卷.docx', teacher=teacher, answer_space_mm=space)
    links = '\n'.join(f"{v['number']}. [[{bank.note_paths[v['question']['id']].relative_to(bank.root).with_suffix('').as_posix()}|{ui.clean_title(v['question']['title'])}]]（{v['score']:g} 分）" for v in items)
    lb.atomic(out / '试卷.md', f'# {title}\n\n总分：{manifest["total_score"]:g}\n\n{links}\n\n```tizhuang-paper\n```\n\n[无答案 Word](打印稿/试卷.docx) · [教师答案 Word](教师稿/试卷.docx)\n\n[无答案打印稿](打印稿/试卷.html) · [教师打印稿](教师稿/试卷.html)\n\n本卷保存了生成时的题目快照与本卷分值，题库原始分值不变。\n')
    for q in chosen:
        if bank.note_paths[q['id']].read_bytes() != originals[q['id']]:
            raise ValueError('组卷期间题目发生修改，请刷新题库后重试')
    # Explicit UI confirmation may promote drafts, without rewriting custom properties/body.
    for q in draft:
        path = bank.note_paths[q['id']]
        original = originals[q['id']].decode('utf-8-sig')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n', original, re.S)
        meta = yaml.safe_load(match[1])
        meta.pop('status', None)
        meta['审核状态'] = '已核对'
        lb.atomic(bank.root / '.bank/backups' / f'{q["id"]}-{uuid.uuid4().hex}.md', originals[q['id']])
        lb.atomic(path, '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n' + original[match.end():])
    manifest['output_hashes'] = {p.relative_to(out).as_posix(): lb.digest(p.read_bytes()) for p in out.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    lb.atomic(out / 'manifest.json', lb.json_text(manifest))
    final_out.parent.mkdir(parents=True, exist_ok=True)
    out.rename(final_out)
    return outputs(final_out, manifest)
