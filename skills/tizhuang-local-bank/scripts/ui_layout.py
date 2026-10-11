"""Chinese filesystem presentation; IDs and portable contracts stay stable."""
import json
from pathlib import Path
import re
import html

QUESTION_DIR = "题目库"
PAPER_DIR = "试卷"
ASSET_DIR = "附件"
KNOWLEDGE_DIR = "知识库/标准知识点"
PERSONAL_DIR = "知识库/我的教学笔记"
TEXTBOOK_DIR = "教材目录"

PROPERTIES = {"schema": "数据格式", "id": "题目编号", "title": "题目名称", "content_format": "正文格式", "status": "审核状态", "type": "题型", "score": "分值", "difficulty": "难度", "subject_id": "学科编号", "phase_id": "学段编号", "grade_id": "年级编号", "edition_id": "教材版本编号", "knowledge_tree_ids": "知识节点编号", "knowledge_ids": "精确知识编号", "chapter_ids": "教材章节编号", "tags": "标签", "search_text": "检索文字", "created_at": "创建时间", "updated_at": "更新时间", "source_kind": "来源类型", "source_provider": "来源平台", "source_external_id": "来源题号", "source_label": "来源说明"}


def name(value):
    value = re.sub(r"<[^>]+>", "", str(value))
    value = re.sub(r'[<>:"/\\|?*\[\]#^\x00-\x1f]', " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")[:55]
    if not value or value.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
        value = "未命名"
    return value


def read(path, default):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def labels(root):
    return read(Path(root) / ".bank/catalog/names.json", {"subjects": {}, "phases": {}, "editions": {}})


def scope_name(root, subject, phase, edition=None):
    catalog = labels(root)
    text = catalog.get("phases", {}).get(str(phase), f"学段{phase}") + " · " + catalog.get("subjects", {}).get(str(subject), f"学科{subject}")
    if edition is not None:
        text += " · " + catalog.get("editions", {}).get(str(edition), f"教材版本{edition}")
    return name(text)


def mappings(root):
    return read(Path(root) / ".bank/ui-paths.json", {"knowledge": {}, "chapters": {}})


def assign_paths(root, nodes, subject, phase, edition=None):
    scope = f"{subject}-{phase}" + (f"-{edition}" if edition is not None else "")
    kind = "chapters" if edition is not None else "knowledge"
    base = Path(("资料/教材目录" if modern(root) else TEXTBOOK_DIR) if edition is not None else ("资料/知识目录" if modern(root) else KNOWLEDGE_DIR)) / scope_name(root, subject, phase, edition)
    mapping = mappings(root)
    existing = mapping[kind].get(scope, {})
    all_nodes = {str(n["id"]): n for n in nodes}
    children = {str(n["parent_id"]) for n in nodes if n.get("parent_id") not in (None, 0, "0")}
    paths = {}
    reserved = set(existing.values())
    for key, node in all_nodes.items():
        if key in existing:
            paths[key] = existing[key]
            continue
        ancestors = []
        parent = str(node.get("parent_id"))
        while parent in all_nodes:
            ancestors.insert(0, name(all_nodes[parent]["name"]))
            parent = str(all_nodes[parent].get("parent_id"))
        # Limit depth for Windows path length; full parent/child links remain.
        folder = base.joinpath(*ancestors[:2])
        filename = name(node["name"])
        path = folder / (filename + ".md")
        counter = 2
        while path.as_posix() in reserved:
            path = folder / f"{filename}（{counter}）.md"
            counter += 1
        paths[key] = path.as_posix()
        reserved.add(paths[key])
    mapping[kind][scope] = paths
    return mapping, paths, base


def link(root, kind, scope, node, label=None):
    path = mappings(root).get(kind, {}).get(scope, {}).get(str(node))
    if not path:
        return str(label or "未下载的关联节点")
    return f"[[{path[:-3]}|{label or Path(path).stem}]]"


def question_path(root, q):
    folder = Path(root) / QUESTION_DIR
    if modern(root):
        folder /= question_group(root, q)
    stem = ('图 · ' if re.search(r'!\[|<img\b', q['content']) else '') + name(q['title'])
    candidate = folder / (stem + ".md")
    counter = 2
    while candidate.exists():
        candidate = folder / f"{stem}（{counter}）.md"
        counter += 1
    return candidate


def asset_path(root, relative):
    root = Path(root).resolve()
    relative = str(relative).replace("\\", "/")
    if any(p in ("", ".", "..") or ":" in p for p in relative.split("/")) or relative.startswith("/"):
        raise ValueError("非法附件路径")
    if relative.startswith("Assets/"):
        candidate = Path(root) / asset_dir(root) / relative[len("Assets/"):]
        if not candidate.exists():
            candidate = Path(root) / ASSET_DIR / relative[len("Assets/"):]
        if candidate.exists():
            if root not in candidate.resolve().parents:
                raise ValueError("附件超出题库")
            return candidate
    target = root / relative
    if root not in target.resolve().parents:
        raise ValueError("附件超出题库")
    return target


def modern(root):
    return bool(root) and read(Path(root) / ".bank/config.json", {}).get("ui_layout") == "teacher/v2"


def asset_dir(root):
    return "资料/附件" if modern(root) else ASSET_DIR


def clean_title(value, kind="题目"):
    value = str(value or "")
    value = re.sub(r'!\[[^\]]*\]\([^\n]*?\)|!\[\[[^\]]+\]\]|<img\b[^>]*>', ' ', value, flags=re.I)
    value = re.sub(r'!\[[^\]]*\]\([^\n]*$|!\[[^\n]*$', ' ', value)
    value = re.sub(r'<[^>]+>|https?://\S+', ' ', value)
    value = html.unescape(value)
    value = re.sub(r'\\[\[\]()]', '', value)
    value = re.sub(r'^网站题目[：:]\s*', '', value)
    value = re.sub(r'\s+', ' ', value).strip(' \n#*')
    return value[:55] or f"{kind}（见原图）"


def native_tags(values):
    # One canonical field; old Chinese 标签 is accepted only when tags is absent.
    if isinstance(values, str):
        values = re.split(r'[,，\s]+', values)
    result = []
    for value in values or []:
        tag = str(value).strip().lstrip('#')
        tag = re.sub(r'[^\w\u4e00-\u9fff/\-]', '_', tag).strip('/_')
        tag = re.sub(r'/+', '/', tag)
        if not tag:
            continue
        if tag.isdecimal():
            tag = '标签/' + tag
        if tag not in result:
            result.append(tag)
    return result


def question_group(root, q):
    prefix = scope_name(root, q.get('subject_id'), q.get('phase_id')) if q.get('subject_id') and q.get('phase_id') else '未指定学科'
    group = '待分类'
    if q.get('knowledge_tree_ids'):
        data = read(Path(root) / f".bank/taxonomy/{q.get('subject_id')}-{q.get('phase_id')}.json", {})
        nodes = {str(n['id']): n for n in data.get('nodes', [])}
        n = nodes.get(str(q['knowledge_tree_ids'][0]))
        seen = set()
        while n and str(n.get('parent_id')) in nodes and str(n['id']) not in seen:
            seen.add(str(n['id']))
            n = nodes[str(n['parent_id'])]
        if n:
            group = n['name']
    elif q.get('chapter_ids') and q.get('edition_id'):
        data = read(Path(root) / f".bank/textbooks/{q.get('subject_id')}-{q.get('phase_id')}-{q.get('edition_id')}.json", {})
        nodes = {str(n['id']): n for n in data.get('nodes', [])}
        n = nodes.get(str(q['chapter_ids'][0]))
        if n:
            group = labels(root).get('editions', {}).get(str(q['edition_id']), '教材') + ' · ' + n['name']
    return Path(name(prefix)) / name(group)
