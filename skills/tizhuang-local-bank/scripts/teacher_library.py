"""Teacher-facing navigation and recoverable layout migration. No online calls."""
from pathlib import Path
import datetime as dt
import json
import os
import re
import uuid
import zipfile
import yaml
import ui_layout as ui


def enrich(root, q, raw=None):
    """Map exact, unambiguous website labels only within the confirmed subject/phase."""
    tree = ui.read(Path(root) / f".bank/taxonomy/{q.get('subject_id')}-{q.get('phase_id')}.json", {}).get('nodes', [])
    names = {}
    for n in tree:
        names.setdefault(n['name'].strip(), []).append(n)
    raw = raw or {}
    words = re.split(r'[,，、]', raw.get('knowledges', '')) if isinstance(raw.get('knowledges'), str) else []
    ids = list(map(str, q.get('knowledge_tree_ids', [])))
    for word in words:
        found = names.get(word.strip(), [])
        if len(found) == 1 and str(found[0]['id']) not in ids:
            ids.append(str(found[0]['id']))
    q['knowledge_tree_ids'] = ids
    exact = list(map(str, q.get('knowledge_ids', [])))
    tags = list(q.get('tags', []))
    for n in tree:
        if str(n['id']) in ids:
            if n.get('knowledge_id') is not None and str(n['knowledge_id']) not in exact:
                exact.append(str(n['knowledge_id']))
            tags.append('考点/' + n['name'])
    q['knowledge_ids'] = exact
    q['tags'] = ui.native_tags(tags)
    q['title'] = ui.clean_title(q.get('title') or q['content'], q.get('type') or '题目')
    if re.search(r'!\s*\[|!\s*\(', q['title']) or q['title'].endswith('（见原图）'):
        q['title'] = ui.clean_title(q['content'], q.get('type') or '题目')
    return q


def classify(bank, args):
    """Apply an Agent's checked knowledge-node plan; never infer IDs by fuzzy names."""
    import local_bank as lb
    payload = lb.read_json(args.file)
    items = payload.get('items')
    if payload.get('schema') != 'tizhuang.classification/v1' or not isinstance(items, list) or not 1 <= len(items) <= 500:
        raise ValueError('分类清单必须使用 tizhuang.classification/v1，包含 1–500 道题')
    questions = {q['id']: q for q in bank.questions()}
    changes, rows, seen = [], [], set()
    for item in items:
        qid = str(item.get('id', ''))
        if qid not in questions or qid in seen:
            raise ValueError('题目不存在或分类清单 ID 重复')
        seen.add(qid)
        q = questions[qid]
        expected = lb.digest('\n'.join(q[k] for k in ('content', 'answer', 'analysis')).encode('utf-8'))
        if item.get('expected_content_sha256') != expected:
            raise ValueError('题目内容已改变，请重新查看后分类：' + qid)
        ids = item.get('knowledge_tree_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 12:
            raise ValueError('每题请选择 1–12 个真实知识节点，无法确定的题先留在报告中')
        if not isinstance(item.get('reason'), str) or not item['reason'].strip():
            raise ValueError('分类清单缺少判断依据')
        tree = bank.taxonomy(q.get('subject_id'), q.get('phase_id'))
        ids = list(dict.fromkeys(map(str, ids)))
        if any(n not in tree for n in ids):
            raise ValueError('知识节点不属于该题学科学段：' + qid)
        ids = list(dict.fromkeys([*q['knowledge_tree_ids'], *ids]))
        if any(n not in tree for n in ids):
            raise ValueError('题目原有知识节点已不在本地目录中，请先核对：' + qid)
        exact = list(dict.fromkeys([*q['knowledge_ids'], *[str(tree[n]['knowledge_id']) for n in ids if tree[n].get('knowledge_id') is not None]]))
        tags = ui.native_tags([*q['tags'], *['考点/' + tree[n]['name'] for n in ids]])
        path = bank.note_paths[qid]
        before = path.read_bytes()
        text = before.decode('utf-8-sig')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n', text, re.S)
        meta = yaml.safe_load(match[1])
        for key in ('knowledge_tree_ids', 'knowledge_ids', '标签'):
            meta.pop(key, None)
        meta['知识节点编号'], meta['精确知识编号'], meta['tags'] = ids, exact, tags
        tail = text[match.end():]
        scope = f"{q['subject_id']}-{q['phase_id']}"
        links = '\n'.join('- ' + ui.link(bank.root, 'knowledge', scope, n, tree[n]['name']) for n in ids)
        managed = '<!-- bank:knowledge:start -->\n## 知识点分类\n\n' + links + '\n<!-- bank:knowledge:end -->'
        pattern = r'<!-- bank:knowledge:start -->.*?<!-- bank:knowledge:end -->'
        if '<!-- bank:knowledge:' in tail and len(re.findall(pattern, tail, re.S)) != 1:
            raise ValueError('知识关联区块标记不完整，请检查：' + qid)
        if re.search(pattern, tail, re.S):
            tail = re.sub(pattern, lambda _: managed, tail, flags=re.S)
        else:
            tail += '\n' + managed + '\n'
        after = ('---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n' + tail).encode('utf-8')
        if before != after:
            changes.append((path, before, after))
        record_path = bank.root / '.bank/records' / (qid + '.json')
        if record_path.exists():
            record_before = record_path.read_bytes()
            record = lb.read_json(record_path)
            record.update(knowledge_tree_ids=ids, knowledge_ids=exact, tags=tags)
            record_after = lb.json_text(record).encode('utf-8')
            if record_before != record_after:
                changes.append((record_path, record_before, record_after))
        rows.append({'id': qid, 'title': q['title'], 'knowledge': [{'id': n, 'name': tree[n]['name']} for n in ids], 'reason': item['reason']})
    if getattr(args, 'plan', False):
        return {'action': 'plan', 'questions': rows, 'files_to_update': len(changes)}
    if not changes:
        return {'action': 'unchanged', 'questions': len(rows)}
    folder = bank.root / '.bank/classification' / (dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    folder.mkdir(parents=True)
    with zipfile.ZipFile(folder / 'backup.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for path, before, _ in changes:
            z.writestr(path.relative_to(bank.root).as_posix(), before)
    lb.atomic(folder / 'plan.json', lb.json_text(payload))
    written = []
    try:
        for path, before, after in changes:
            if path.read_bytes() != before:
                raise ValueError('题目正在被编辑，停止分类：' + str(path))
            lb.atomic(path, after)
            written.append((path, before, after))
    except Exception:
        for path, before, after in reversed(written):
            if path.read_bytes() == after:
                lb.atomic(path, before)
        raise
    lb.atomic(folder / 'result.json', lb.json_text(rows))
    bank.questions()
    return {'action': 'classified', 'questions': len(rows), 'backup': str(folder / 'backup.zip'), 'report': str(folder / 'result.json')}


def dashboard(bank, questions):
    import local_bank as lb
    paths = {lb.read_note(p)['id']: p.relative_to(bank.root).with_suffix('').as_posix() for p in (bank.root / ui.QUESTION_DIR).rglob('*.md')}
    groups = {}
    for q in questions:
        groups.setdefault(ui.question_group(bank.root, q).as_posix(), []).append(q)
    reviewed = sum(q['status'] == 'reviewed' for q in questions)
    papers = list((bank.root / ui.PAPER_DIR).glob('*/试卷.md'))
    text = f"# 题库首页\n\n共 **{len(questions)}** 题 · 已核对 **{reviewed}** 题 · 待核对 **{len(questions)-reviewed}** 题 · 试卷 **{len(papers)}** 份\n\n"
    text += '> 点击左侧书库图标打开题库工作台，可按教材、知识点和标签筛选。\n\n```tizhuang-dashboard\n```\n\n'
    text += '## 我的题目\n\n'
    for group, rows in sorted(groups.items()):
        text += f"### {group.replace('/', ' · ')}（{len(rows)}）\n\n"
        for q in rows:
            title = ui.clean_title(q['title']).replace('|', '｜').replace('[', '（').replace(']', '）')
            image = '[图] ' if re.search(r'!\[|<img\b', q['content']) else ''
            text += f"- {image}[[{paths[q['id']]}|{title}]] · {q['type']} · {'已核对' if q['status']=='reviewed' else '待核对'}\n"
        text += '\n'
    text += '## 最近导入\n\n'
    imports = sorted((bank.root / '待整理').glob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True)[:8]
    text += '\n'.join(f"- [[待整理/{p.stem}|{p.stem}]]" for p in imports) or '暂无导入任务。'
    paper_links = []
    for p in papers:
        manifest = ui.read(p.parent / 'manifest.json', {})
        heading = re.search(r'^#\s+(.+)$', p.read_text(encoding='utf-8'), re.M)
        title = str(manifest.get('title') or (heading[1] if heading else p.parent.name)).replace('|', '｜')
        paper_links.append(f"- [[{p.relative_to(bank.root).with_suffix('').as_posix()}|{title}]]")
    text += '\n\n## 我的试卷\n\n' + ('\n'.join(paper_links) or '核对题目后，可在 Agent 中按题目、章节或标签组卷。')
    text += '\n\n## 使用说明\n\n- 原件、图片和目录快照放在「资料」，平时无需逐个打开。\n- 自己的备课记录放在「教学笔记」。\n- 每题只存一份，多知识点和标签可以同时关联。\n'
    target = bank.root / '题库首页.md'
    if not target.exists() or target.read_text(encoding='utf-8') != text:
        lb.atomic(target, text)
    return {'path': str(target), 'questions': len(questions), 'reviewed': reviewed, 'groups': len(groups)}


def organize(bank):
    import local_bank as lb
    root = bank.root.resolve()
    if ui.modern(root):
        return {'action': 'already_organized', **dashboard(bank, bank.questions())}
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    backup = root.parent / f'题库整理备份-{stamp}.zip'
    before = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    with zipfile.ZipFile(backup, 'w', zipfile.ZIP_DEFLATED) as archive:
        for rel in sorted(before):
            archive.write(lb.inside(root, rel), rel)
    moves = [('附件', '资料/附件'), ('教材目录', '资料/教材目录'), ('知识库/标准知识点', '资料/知识目录'), ('知识库/我的教学笔记', '教学笔记'), ('打印稿', '试卷/历史打印稿')]
    pathmap = {}
    archived = []
    def move(old, new):
        source, target = lb.inside(root, old), lb.inside(root, new)
        if not source.exists():
            return
        if target.exists():
            raise ValueError(f'整理目标已存在，停止以免覆盖：{new}')
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        pathmap[old] = new
    try:
        questions = bank.questions()
        old_paths = dict(bank.note_paths)
        contents = {q['id']: old_paths[q['id']].read_text(encoding='utf-8-sig') for q in questions}
        for old, new in moves:
            move(old, new)
        for filename in ('题库入口.md', '题目导航.md', '网站取题导航.md', '插件测试说明.md'):
            move(filename, '资料/旧导航/' + filename)
        if (root / '知识库/知识库导航.md').exists():
            move('知识库/知识库导航.md', '资料/知识目录/知识库导航.md')
        for path in root.glob('未命名*.base'):
            if yaml.safe_load(path.read_text(encoding='utf-8-sig')) == {'views': [{'type': 'table', 'name': '视图'}]}:
                move(path.name, f'.bank/archived-ui/{stamp}/{path.name}')
                archived.append(path.name)
        cfg = lb.read_json(root / '.bank/config.json')
        cfg['ui_layout'] = 'teacher/v2'
        lb.atomic(root / '.bank/config.json', lb.json_text(cfg))
        for q in questions:
            record = ui.read(root / f".bank/records/{q['id']}.json", {})
            enrich(root, q, record.get('original_payload', {}))
            old = old_paths[q['id']]
            target = ui.question_path(root, q)
            original = contents[q['id']]
            m = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n', original, re.S)
            meta = yaml.safe_load(m[1])
            for key in ('title', 'knowledge_tree_ids', 'knowledge_ids'):
                meta[ui.PROPERTIES[key]] = q[key]
            meta.pop('标签', None)
            meta['tags'] = q['tags']
            prefix = os.path.relpath(root / ui.asset_dir(root), target.parent).replace('\\', '/') + '/'
            body = re.sub(r'(?:\.\./)+(?:资料/)?(?:附件|Assets)/', lambda _: prefix, original[m.end():])
            newtext = '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n' + body
            target.parent.mkdir(parents=True, exist_ok=True)
            old.rename(target)
            lb.atomic(target, newtext)
            pathmap[old.relative_to(root).as_posix()] = target.relative_to(root).as_posix()
        # Longest path first: rewrite links and saved question paths, never credentials.
        def replace_paths(text, paper=False):
            for old, new in sorted(pathmap.items(), key=lambda v: -len(v[0])):
                if paper and old == '打印稿':
                    continue
                text = re.sub(r'(?<![\w/])' + re.escape(old) + r'(?=$|[/\]|#"\s)])', lambda _: new, text)
                if old.endswith('.md'):
                    text = text.replace('[[' + old[:-3] + '|', '[[' + new[:-3] + '|').replace('[[' + old[:-3] + ']]', '[[' + new[:-3] + ']]')
            return text
        for path in root.rglob('*.md'):
            if '.bank' in path.relative_to(root).parts or '.obsidian' in path.relative_to(root).parts:
                continue
            text = path.read_text(encoding='utf-8-sig')
            newtext = replace_paths(text, paper=(path.name == '试卷.md' and (path.parent / 'manifest.json').exists()))
            if newtext != text:
                lb.atomic(path, newtext)
        def remap(value):
            if isinstance(value, str):
                return replace_paths(value)
            if isinstance(value, list):
                return [remap(v) for v in value]
            if isinstance(value, dict):
                return {k: remap(v) for k, v in value.items()}
            return value
        for rel in ('.bank/ui-paths.json', '.bank/pending/questions.json', '.obsidian/workspace.json'):
            if (root / rel).exists():
                lb.atomic(root / rel, lb.json_text(remap(lb.read_json(root / rel))))
        obsidian = root / '.obsidian/app.json'
        settings = ui.read(obsidian, {})
        settings['attachmentFolderPath'] = '资料/附件'
        lb.atomic(obsidian, lb.json_text(settings))
        for path in sorted([p for p in (root / '知识库').rglob('*') if p.is_dir()], key=lambda p: len(p.parts), reverse=True) if (root / '知识库').exists() else []:
            if not any(path.iterdir()):
                path.rmdir()
        if (root / '知识库').exists() and not any((root / '知识库').iterdir()):
            (root / '知识库').rmdir()
        after = bank.questions()
        old_by_id = {q['id']: q for q in questions}
        for q in after:
            for key in ('content', 'answer', 'analysis', 'status'):
                if q[key] != old_by_id[q['id']][key]:
                    raise ValueError('整理改变了题目正文或审核状态，回滚')
            lb.verify_media(bank, q)
        result = {'action': 'organized', 'backup': str(backup), 'questions': len(after), 'archived_empty_views': archived, 'moved': pathmap}
        lb.atomic(root / '.bank/last-organization.json', lb.json_text(result))
        return result
    except Exception:
        # Restore the exact snapshot. Delete only verified individual files created here.
        for p in list(root.rglob('*')):
            if p.is_file() and p.relative_to(root).as_posix() not in before:
                lb.inside(root, p.relative_to(root).as_posix()).unlink()
        with zipfile.ZipFile(backup) as archive:
            for rel in archive.namelist():
                lb.atomic(lb.inside(root, rel), archive.read(rel))
        for p in sorted([p for p in root.rglob('*') if p.is_dir()], key=lambda p: len(p.parts), reverse=True):
            if not any(p.iterdir()):
                p.rmdir()
        raise
