"""Conservative offline knowledge matching, with explicit Agent handoff for ambiguity."""
from pathlib import Path
from types import SimpleNamespace
import datetime as dt
import json
import re
import uuid


def suggest(q, nodes):
    """Trust exact named teaching tags, never short keywords occurring in a stem."""
    from ui_layout import native_tags
    names = {}
    for n in nodes.values():
        # Obsidian tags replace punctuation with underscores. Apply the same
        # normalization to the catalog label, while retaining ambiguity checks.
        aliases = {n['name'].strip(), *native_tags([n['name'].strip()])}
        for alias in aliases:
            names.setdefault(alias, []).append(n)
    tags = {str(t).split('/')[-1].strip() for t in q.get('tags', [])}
    # Imported website labels are handled by enrich(); here only teacher/Agent tags
    # are evidence. A mention of e.g. '圆' in a long word must not classify a question.
    matches, ambiguous = [], []
    for tag in sorted(tags):
        found = names.get(tag, [])
        if len(found) == 1:
            matches.append((str(found[0]['id']), '已有标签「' + tag + '」与本学科学段知识点完全匹配'))
        elif len(found) > 1:
            ambiguous.append(tag)
    if ambiguous:
        return [], '同名知识点有多个位置，需要 Agent 核对：' + '、'.join(ambiguous)
    if len(matches) > 12:
        return [], '候选知识点超过 12 个，需要核对核心考点'
    if matches:
        return matches, ''
    return [], '缺少可直接对应的考点标签，需要 Agent 阅读题目判断'


def run(bank, args):
    import local_bank as lb
    from teacher_library import classify
    questions = bank.questions()
    selected = set(getattr(args, 'ids', None) or [])
    batch = getattr(args, 'batch', None)
    if batch:
        if not re.fullmatch(r'[a-f0-9]{24}', batch):
            raise ValueError('PDF 批次编号无效')
        manifest = lb.read_json(bank.root / '.bank/imports' / batch / 'manifest.json')
        selected = set(manifest.get('imported', {}).values())
    if selected and not selected.issubset({q['id'] for q in questions}):
        raise ValueError('待分类题目已变化，请刷新后重试')
    if batch or selected:
        questions = [q for q in questions if q['id'] in selected]
    questions = [q for q in questions if not q.get('knowledge_tree_ids')]
    if len(questions) > 500:
        raise ValueError('一次最多处理 500 道未关联知识点的题目，请按批次分开处理')
    items, pending = [], []
    for q in questions:
        tree_path = bank.root / f".bank/taxonomy/{q.get('subject_id')}-{q.get('phase_id')}.json"
        nodes = bank.taxonomy(q['subject_id'], q['phase_id']) if tree_path.exists() else {}
        matches, reason = suggest(q, nodes) if nodes else ([], '尚未下载该学科学段的知识树')
        if matches:
            items.append({'id': q['id'], 'knowledge_tree_ids': [n for n, _ in matches],
                          'expected_content_sha256': lb.digest('\n'.join(q[k] for k in ('content', 'answer', 'analysis')).encode()),
                          'reason': '；'.join(r for _, r in matches)})
        else:
            pending.append({'id': q['id'], 'title': q['title'], 'reason': reason})
    if not questions:
        return {'classified': 0, 'pending': 0, 'considered': 0, 'message': '所有题目都已关联知识点'}
    folder = bank.root / '.bank/classification' / ('auto-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    folder.mkdir(parents=True)
    plan = folder / 'plan.json'
    lb.atomic(plan, lb.json_text({'schema': 'tizhuang.classification/v1', 'items': items}))
    applied = classify(bank, SimpleNamespace(file=plan, plan=False)) if items else {}
    result = {'classified': len(items), 'pending': len(pending), 'considered': len(questions),
              'pending_questions': pending, 'backup': applied.get('backup'), 'plan': str(plan)}
    lb.atomic(folder / 'result.json', lb.json_text(result))
    report = bank.root / '待整理' / ('知识点自动分类 · ' + folder.name + '.md')
    lines = ['# 知识点自动分类', '', f'已关联 {len(items)} 题 · 待 Agent 判断 {len(pending)} 题。', '',
             '依据已有标签精确匹配本地知识树；不使用网站题目额度。教材章节、原文和核对状态保持原样。', '']
    byid = {q['id']: q for q in questions}
    for item in items:
        lines.extend(['- 已关联：' + byid[item['id']]['title'], '  - ' + item['reason']])
    for item in pending:
        note = bank.note_paths[item['id']].relative_to(bank.root).with_suffix('').as_posix()
        lines.extend(['- [[' + note + '|' + item['title'].replace('|', '｜') + ']]', '  - ' + item['reason']])
    lines.extend(['', '## Agent 继续处理', '', '只处理本报告待判断的题目，阅读题干、配图、原答案和解析，查找本地对应学科学段的标准知识树。'
                  '按真实节点生成 tizhuang.classification/v1 清单，经 classify --plan 验证后应用。不要猜教材，不改变正文或审核状态。', '',
                  '任务记录：`' + str(folder.relative_to(bank.root)) + '/result.json`'])
    lb.atomic(report, '\n'.join(lines) + '\n')
    result['report'] = str(report)
    return result
