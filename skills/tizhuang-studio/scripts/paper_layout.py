"""Shared question grouping for Word and browser paper renderers."""
from decimal import Decimal


def kind(value):
    value = str(value or '其他题').strip() or '其他题'
    return {'单选题':'选择题', '单项选择题':'选择题', '填空':'填空题'}.get(value, value)


def groups(manifest):
    result = {}
    for item in manifest['items']:
        name = kind(item['question'].get('type'))
        result.setdefault(name, []).append(item)
    number = 0
    rows = []
    for index, (name, items) in enumerate(result.items(), 1):
        score = sum((Decimal(str(i['score'])) for i in items), Decimal(0))
        label = '一二三四五六七八九十'[index-1] if index <= 10 else str(index)
        row = {'title': f'{label}、{name}（共 {len(items)} 题，合计 {score.normalize():f} 分）', 'items': []}
        for item in items:
            number += 1
            row['items'].append({**item, 'number': number})
        rows.append(row)
    return rows


def grouped_manifest(manifest):
    return {**manifest, 'items': [item for group in groups(manifest) for item in group['items']]}


def needs_space(question):
    return not any(t in str(question.get('type', '')) for t in ('选择','单选','多选','判断','填空'))
