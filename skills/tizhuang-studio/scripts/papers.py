"""Saved-paper labels and reopening; never alter exported files or questions."""
import copy
import json
import re


def snapshot(root, ident):
    if not isinstance(ident, str) or not re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{8}', ident):
        raise ValueError('试卷编号无效。')
    try:
        data = json.loads((root / 'exports' / ident / 'snapshot.json').read_text(encoding='utf-8'))
        if not isinstance(data.get('items'), list) or not data['items']:
            raise ValueError()
        return data
    except (OSError, ValueError, TypeError, AttributeError):
        raise ValueError('本卷快照缺失或损坏，暂时不能继续编辑；已有下载文件仍可使用。') from None


def summary(root, ident):
    try:
        data = snapshot(root, ident)
        scopes = sorted({(str(i['question'].get('phase_id', '')), str(i['question'].get('subject_id', ''))) for i in data['items']})
        return {'snapshot_available': True, 'total_score': sum(i['score'] for i in data['items']),
                'duration_minutes': data['duration_minutes'],
                'classifications': [{k: i['question'].get(k) for k in
                    ('subject_id','phase_id','edition_id','knowledge_tree_ids','chapter_ids','knowledge')}
                    for i in data['items']],
                'scopes': [{'phase_id': p, 'subject_id': s} for p, s in scopes]}
    except (ValueError, KeyError, TypeError):
        return {'snapshot_available': False}


def apply(root, body, state, questions, number):
    paper = next((e for e in state['exports'] if e['id'] == body.get('id')), None)
    if paper is None:
        raise ValueError('找不到这份试卷，请刷新列表。')
    if body['action'] == 'paper-update':
        title, tags = body.get('title'), body.get('tags', [])
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError('试卷名称须为 1–120 字。')
        if not isinstance(tags, list) or len(tags) > 10 or any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 24 for t in tags):
            raise ValueError('最多 10 个标签，每个标签为 1–24 字。')
        paper['display_title'] = title.strip()
        paper['tags'] = list(dict.fromkeys(t.strip() for t in tags))
        return
    if body.get('confirm') is not True:
        raise ValueError('继续编辑将替换当前组卷篮，请先确认。')
    data = snapshot(root, paper['id'])
    items = []
    for item in data['items']:
        ident = item.get('question', {}).get('id')
        q = questions.get(ident)
        if not q or q.get('archived') or q.get('prepare_error'):
            raise ValueError('本卷含已归档、缺失或附件不完整的题目，请先恢复题目再编辑。')
        if any(i['id'] == ident for i in items):
            raise ValueError('本卷快照含重复题目，暂时不能继续编辑。')
        items.append({'id': ident, 'score': number(item.get('score'), 0, 1000)})
    if len(items) > 200:
        raise ValueError('每卷最多 200 题。')
    duration = number(data.get('duration_minutes'), 1, 600, True)
    space = number(data.get('answer_space_mm', 20), 0, 100, True)
    state['previous_basket'] = copy.deepcopy({k: state.get(k) for k in ('items', 'title', 'duration_minutes', 'answer_space_mm', 'editing_paper_id')})
    state.update(items=items, title=paper.get('display_title') or paper['title'], duration_minutes=duration,
                 answer_space_mm=space, editing_paper_id=paper['id'])
