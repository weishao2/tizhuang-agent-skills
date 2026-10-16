#!/usr/bin/env python3
"""Independent, file-first Obsidian question bank. Python 3.10+."""
import argparse
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from types import SimpleNamespace
import re
import sqlite3
import sys
import tempfile
import urllib.request
from urllib.parse import urlsplit
import uuid
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_layout as ui

try:
    import markdown
    import yaml
    from latex2mathml.converter import convert as mathml
except ImportError as _exc:  # missing dependencies must still produce machine-readable JSON
    print(json.dumps({"ok": False, "kind": "missing_dependency", "error": "缺少运行依赖：" + str(_exc),
                      "hint": "请使用本 skill 的独立 Python 环境，执行 pip install -r scripts/requirements.txt；或运行 doctor.py 查看缺少哪一项。"}))
    sys.exit(1)

SCHEMA = "tizhuang.question/v1"
PACKAGE = "tizhuang.question-package/v1"
DEFAULT_API = "https://tizhuang.qcscience.cc/api"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(data, bytes):
        data = data.encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def safe_relative(value):
    value = str(value).replace("\\", "/")
    parts = value.split("/")
    if not value or value.startswith("/") or any(p in ("", ".", "..") or ":" in p for p in parts):
        raise ValueError(f"非法相对路径: {value}")
    return value


def inside(root, relative):
    root = Path(root).resolve()
    target = (root / safe_relative(relative)).resolve()
    if root not in target.parents:
        raise ValueError("路径超出题库")
    return target


class SafeHTML(HTMLParser):
    tags = {"p", "br", "div", "span", "strong", "b", "em", "i", "u", "s", "sub", "sup", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th", "blockquote", "pre", "code", "hr", "img", "a", "h1", "h2", "h3", "h4", "math", "mrow", "mi", "mn", "mo", "mfrac", "msup", "msub", "msqrt", "mtext", "semantics", "annotation", "msubsup", "mroot", "munder", "mover", "munderover", "mtable", "mtr", "mtd", "mstyle", "mspace", "mpadded", "menclose", "mphantom"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.block = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object", "svg"}:
            self.block += 1
        if self.block or tag not in self.tags:
            return
        clean = []
        for key, val in attrs:
            if key in {"alt", "title", "colspan", "rowspan"}:
                clean.append((key, val or ""))
            if tag in self.tags and tag.startswith("m") and key in {"xmlns", "display", "mathvariant", "stretchy", "fence", "separator", "columnalign", "rowalign", "linethickness", "width", "height", "depth", "notation"}:
                clean.append((key, val or ""))
            if (tag == "img" and key == "src") or (tag == "a" and key == "href"):
                v = (val or "").strip()
                if v and not re.match(r"[a-z][a-z0-9+.-]*:", v, re.I) and not v.startswith("//"):
                    clean.append((key, v))
        self.out.append("<" + tag + "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in clean) + ">")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "object", "svg"}:
            self.block = max(0, self.block - 1)
            return
        if not self.block and tag in self.tags:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.block:
            self.out.append(html.escape(data))


def render(text, fmt="markdown"):
    formulas = {}
    def replace_formula(match):
        token = "BANKMATHTOKEN" + uuid.uuid4().hex.upper()
        expression = next(v for v in match.groups() if v is not None)
        # Website Markdown escapes literal answer brackets like \[ NBSP \].
        # An empty answer space is not a formula; preserve its visible brackets
        # and whitespace instead of passing it to the TeX converter.
        if not expression.strip():
            brackets = ("[", "]") if match[0].startswith("\\[") else ("(", ")") if match[0].startswith("\\(") else ("", "")
            formulas[token] = html.escape(brackets[0] + expression + brackets[1])
            return token
        try:
            formulas[token] = mathml(expression, display="block" if match[0].startswith(("$$", "\\[")) else "inline")
        except Exception as exc:
            raise ValueError(f"公式无法转换，请检查 LaTeX: {expression[:80]!r}") from exc
        return token
    text = re.sub(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]|\\\((.+?)\\\)|(?<!\\)\$([^$\n]+?)(?<!\\)\$", replace_formula, text, flags=re.S)
    raw = text if fmt == "html" else markdown.markdown(text, extensions=["tables", "fenced_code"])
    for token, formula in formulas.items():
        raw = raw.replace(token, formula)
    parser = SafeHTML()
    parser.feed(raw)
    return "".join(parser.out)


def validate_tree(nodes):
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("知识树为空或不是数组")
    mapping = {}
    for node in nodes:
        if not isinstance(node, dict) or "id" not in node or not node.get("name"):
            raise ValueError("知识节点缺少 id/name")
        key = str(node["id"])
        if not re.fullmatch(r"[0-9]+", key):
            raise ValueError("知识树节点 ID 必须为数字")
        if key in mapping:
            raise ValueError("知识节点 ID 重复")
        mapping[key] = node
    for key, node in mapping.items():
        seen = {key}
        parent = node.get("parent_id")
        while parent not in (None, 0, "0", ""):
            parent = str(parent)
            if parent not in mapping:
                raise ValueError(f"知识树缺少父节点: {parent}")
            if parent in seen:
                raise ValueError("知识树存在循环")
            seen.add(parent)
            parent = mapping[parent].get("parent_id")
    return mapping


def normalize(q):
    if q.get("schema", SCHEMA) != SCHEMA:
        raise ValueError("不支持的题目协议版本")
    q = dict(q)
    q["schema"] = SCHEMA
    q.setdefault("id", str(uuid.uuid4()))
    q["id"] = str(q["id"])
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", str(q["id"])):
        raise ValueError("题目 ID 含非法字符")
    for key in ("content", "answer", "analysis"):
        q.setdefault(key, "")
        if not isinstance(q[key], str):
            q[key] = json.dumps(q[key], ensure_ascii=False)
        if "<!-- bank:" in q[key]:
            raise ValueError("正文不能包含题库内部区块标记")
    if not q["content"].strip():
        raise ValueError("题目正文不能为空")
    q.setdefault("title", ui.clean_title(q["content"]))
    q.setdefault("content_format", "markdown")
    if q["content_format"] not in ("markdown", "html"):
        raise ValueError("content_format 必须是 markdown 或 html")
    q.setdefault("status", "draft")
    if q["status"] not in ("draft", "reviewed"):
        raise ValueError("status 必须是 draft 或 reviewed")
    q.setdefault("type", "未分类")
    q.setdefault("score", 5)
    q["score"] = float(q["score"])
    if not 0 < q["score"] <= 1000:
        raise ValueError("分值必须在 0 到 1000 之间")
    for key in ("tags", "knowledge_tree_ids", "knowledge_ids", "chapter_ids", "assets"):
        q.setdefault(key, [])
        if not isinstance(q[key], list):
            raise ValueError(f"{key} 必须是数组")
    for key in ("knowledge_tree_ids", "knowledge_ids", "chapter_ids"):
        q[key] = [str(v) for v in q[key]]
    q["tags"] = ui.native_tags(q["tags"])
    q.setdefault("source", {"kind": "local"})
    q.setdefault("created_at", now())
    q.setdefault("updated_at", q["created_at"])
    return q


def note_text(q, root=None, path=None):
    meta = {k: v for k, v in q.items() if k not in ("content", "answer", "analysis", "source", "assets", "original_payload")}
    # Obsidian properties stay flat; richer provenance is an immutable sidecar.
    meta["source_kind"] = q["source"].get("kind", "local")
    meta["source_provider"] = q["source"].get("provider", "")
    meta["source_external_id"] = str(q["source"].get("external_id", ""))
    meta["source_label"] = q["source"].get("label", "")
    meta = {ui.PROPERTIES.get(k, k): v for k, v in meta.items()}
    meta.pop("标签", None)
    meta["tags"] = ui.native_tags(q.get("tags", []))
    meta["审核状态"] = {"draft": "待核对", "reviewed": "已核对"}[q["status"]]
    body = "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n"
    for key, label in (("content", "题目"), ("answer", "答案"), ("analysis", "解析")):
        prefix = os.path.relpath(Path(root) / ui.asset_dir(root), Path(path).parent).replace('\\', '/') + '/' if root and path else '../' + ui.asset_dir(root) + '/'
        section = q[key].replace("Assets/", prefix)
        body += f"## {label}\n\n<!-- bank:{key}:start -->\n{section}\n<!-- bank:{key}:end -->\n\n"
    if q["knowledge_tree_ids"] and q.get("subject_id") is not None and q.get("phase_id") is not None:
        scope = f"{q['subject_id']}-{q['phase_id']}"
        body += "## 知识关联\n\n" + "\n".join("- " + ui.link(root, "knowledge", scope, node) if root else f"- 知识节点 {node}" for node in q["knowledge_tree_ids"]) + "\n"
    if q["chapter_ids"]:
        scope = f"{q['subject_id']}-{q['phase_id']}-{q['edition_id']}"
        body += "\n## 教材章节\n\n" + "\n".join("- " + ui.link(root, "chapters", scope, node) if root else f"- 教材章节 {node}" for node in q["chapter_ids"]) + "\n"
    return body


def read_note(path):
    text = path.read_text(encoding="utf-8-sig")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not match:
        raise ValueError(f"缺少 YAML 属性: {path}")
    q = yaml.safe_load(match[1])
    if not isinstance(q, dict):
        raise ValueError(f"YAML 属性无效: {path}")
    reverse = {v: k for k, v in ui.PROPERTIES.items()}
    canonical_tags = q.get('tags', q.get('标签', []))
    q = {reverse.get(k, k): v for k, v in q.items()}
    q['tags'] = ui.native_tags(canonical_tags)
    q["status"] = {"待核对": "draft", "已核对": "reviewed"}.get(q.get("status"), q.get("status", "draft"))
    for key in ("content", "answer", "analysis"):
        block = re.findall(rf"<!-- bank:{key}:start -->\r?\n(.*?)\r?\n<!-- bank:{key}:end -->", text, re.S)
        if len(block) != 1:
            raise ValueError(f"区块标记缺失或重复: {path} ({key})")
        q[key] = re.sub(r'(?:\.\./)+(?:资料/)?(?:附件|Assets)/', 'Assets/', block[0])
    q["source"] = {"kind": q.pop("source_kind", "local"), "provider": q.pop("source_provider", ""), "external_id": q.pop("source_external_id", ""), "label": q.pop("source_label", "")}
    return normalize(q)


class Bank:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.readonly = False  # read-only commands must not rewrite the index or navigation notes
        if not (self.root / ".bank/config.json").is_file():
            raise ValueError("题库未初始化，请先运行 init")
        if (self.root / "Questions").exists():
            raise ValueError("检测到旧版英文目录，请先运行 migrate-cn 迁移；原文件不会自动覆盖")

    def questions(self):
        result = []
        ids = set()
        self.note_paths = {}
        for path in sorted((self.root / ui.QUESTION_DIR).rglob("*.md")):
            q = read_note(path)
            if q["id"] in ids:
                raise ValueError(f"题目 ID 重复或与文件名不同: {path}")
            ids.add(q["id"])
            self.note_paths[q["id"]] = path
            side = self.root / ".bank/records" / f'{q["id"]}.json'
            record = read_json(side) if side.exists() else {}
            q["assets"] = record.get("assets", [])
            result.append(q)
        if self.readonly:
            return result
        # Entirely disposable index: always rebuilt to reflect Obsidian edits.
        db = sqlite3.connect(self.root / ".bank/index.sqlite3")
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS questions (id TEXT PRIMARY KEY, payload TEXT)")
            db.execute("DELETE FROM questions")
            db.executemany("INSERT INTO questions VALUES (?, ?)", [(q["id"], json_text(q)) for q in result])
        db.close()
        write_question_navigation(self, result)
        return result

    def taxonomy(self, subject, phase):
        p = self.root / ".bank/taxonomy" / f"{int(subject)}-{int(phase)}.json"
        if not p.exists():
            raise ValueError("该学科学段的知识树尚未下载")
        return validate_tree(read_json(p)["nodes"])

    def chapters(self, subject, phase, edition):
        if None in (subject, phase, edition):
            raise ValueError("教材章节必须指定 subject、phase、edition")
        p = self.root / ".bank/textbooks" / f"{int(subject)}-{int(phase)}-{int(edition)}.json"
        if not p.exists():
            raise ValueError("该教材版本的章节目录尚未下载")
        return validate_tree(read_json(p)["nodes"])

    def save(self, q, base=None):
        q = normalize(q)
        if q["knowledge_tree_ids"]:
            tree = self.taxonomy(q.get("subject_id"), q.get("phase_id"))
            if any(v not in tree for v in q["knowledge_tree_ids"]):
                raise ValueError("题目包含知识树中不存在的节点")
        if q["chapter_ids"]:
            chapters = self.chapters(q.get("subject_id"), q.get("phase_id"), q.get("edition_id"))
            if any(v not in chapters for v in q["chapter_ids"]):
                raise ValueError("题目章节不属于所选教材版本，不能混用章节 ID")
        existing = self.questions()
        # Resolve and verify every attachment before writing any canonical note.
        asset_data = []
        replacements = {}
        for asset in q["assets"]:
            rel = safe_relative(asset["path"])
            if not base:
                raise ValueError("带附件的题目必须提供来源目录")
            data = inside(base, rel).read_bytes()
            sha = digest(data)
            if asset.get("sha256") and sha != asset["sha256"]:
                raise ValueError("附件 SHA256 不一致")
            suffix = Path(rel).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".txt", ".mp3", ".mp4"}:
                raise ValueError(f"不支持的附件类型: {suffix}")
            new = f"Assets/{sha}{suffix}"
            asset_data.append((new, data))
            replacements[rel] = new
        for key in ("content", "answer", "analysis"):
            for old, new in replacements.items():
                q[key] = q[key].replace(old, new)
        q["assets"] = [{"path": rel, "sha256": digest(data)} for rel, data in asset_data]
        # Compare canonical content-addressed paths; repeated PDF crops may have different input names.
        def fingerprint(item):
            scope = [item.get(k) for k in ("subject_id", "phase_id", "grade_id", "edition_id")]
            return digest((json.dumps(scope) + "\n" + item["content"].strip()).encode())
        for old in existing:
            src, prev = q["source"], old["source"]
            same_source = src.get("external_id") and src.get("provider") and src.get("external_id") == prev.get("external_id") and src.get("provider") == prev.get("provider")
            if fingerprint(q) == fingerprint(old):
                return {"id": old["id"], "action": "duplicate"}
            if (same_source and old["content"] != q["content"]) or old["id"] == q["id"]:
                raise ValueError("已有同 ID 或同来源题目的正文不同；请人工处理版本，不自动覆盖")
        for rel, data in asset_data:
            atomic(self.root / ui.asset_dir(self.root) / Path(rel).name, data)
        atomic(self.root / ".bank/records" / f'{q["id"]}.json', json_text(q))
        path = ui.question_path(self.root, q)
        atomic(path, note_text(q, self.root, path))
        write_question_navigation(self, existing + [q])
        return {"id": q["id"], "action": "created"}

    def select(self, args):
        tree_ids = None
        if getattr(args, "knowledge", None):
            if not args.subject or not args.phase:
                raise ValueError("知识节点筛选需要同时指定 subject 和 phase")
            tree = self.taxonomy(args.subject, args.phase)
            if str(args.knowledge) not in tree:
                raise ValueError("知识节点不存在，不能忽略此筛选条件")
            tree_ids = {str(args.knowledge)}
            while True:
                expanded = tree_ids | {key for key, v in tree.items() if str(v.get("parent_id")) in tree_ids}
                if expanded == tree_ids:
                    break
                tree_ids = expanded
        chapter_ids = None
        if getattr(args, "chapter", None):
            chapters = self.chapters(args.subject, args.phase, args.edition)
            if str(args.chapter) not in chapters:
                raise ValueError("章节不属于指定教材版本，不能忽略此条件")
            chapter_ids = {str(args.chapter)}
            while True:
                expanded = chapter_ids | {k for k, v in chapters.items() if str(v.get("parent_id")) in chapter_ids}
                if expanded == chapter_ids:
                    break
                chapter_ids = expanded
        used = set()
        if getattr(args, "unused", False):
            for path in (self.root / ui.PAPER_DIR).glob("*/manifest.json"):
                used.update(v["question"]["id"] for v in read_json(path)["items"])
        selected = []
        for q in self.questions():
            if any(getattr(args, arg, None) is not None and str(q.get(field)) != str(getattr(args, arg)) for arg, field in (("subject", "subject_id"), ("phase", "phase_id"), ("grade", "grade_id"), ("edition", "edition_id"), ("type", "type"), ("status", "status"))):
                continue
            if getattr(args, "tag", None) and not any(t == args.tag or t.startswith(args.tag + '/') for t in q["tags"]):
                continue
            if tree_ids is not None and not tree_ids.intersection(q["knowledge_tree_ids"]):
                continue
            if chapter_ids is not None and not chapter_ids.intersection(q["chapter_ids"]):
                continue
            if getattr(args, "query", None) and args.query.casefold() not in (q["title"] + "\n" + q["content"] + "\n" + q.get('search_text', '') + "\n" + " ".join(q["tags"])).casefold():
                continue
            if q["id"] not in used:
                selected.append(q)
        return selected


def website_questions(payload):
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("网站结果必须是 items 数组或题目数组")
    output = []
    for item in items:
        def parts(v):
            content = v.get("title_html") or v.get("title") or ""
            options = v.get("options_html") or v.get("options") or {}
            # Keep producer order. Never sort or shuffle A/B/C/D.
            content += "".join(f"<p>{html.escape(str(k))}. {val}</p>" for k, val in options.items())
            return content, v.get("answer_html") or v.get("answer") or "", v.get("analysis_html") or v.get("analysis") or ""
        content, answer, analysis = parts(item)
        for n, child in enumerate(item.get("subquestions", []), 1):
            c, a, e = parts(child)
            content += f"<h4>({n})</h4>{c}"
            answer += f"<h4>({n})</h4>{a}"
            analysis += f"<h4>({n})</h4>{e}"
        display_title = html.unescape(re.sub(r"<[^>]+>", "", item.get("title") or item.get("title_html") or ""))
        display_title = re.sub(r"\s+", " ", display_title).strip()[:60]
        output.append({"title": display_title or f"网站题目 {item['id']}", "content": content, "answer": answer, "analysis": analysis, "content_format": "html", "type": item.get("question_type") or "未分类", "subject_id": item.get("subject_id"), "grade_id": item.get("grade_id"), "difficulty": item.get("difficulty"), "source": {"kind": "website", "provider": "tizhuang", "external_id": str(item["id"]), "label": item.get("source") or "题庄网站"}, "original_payload": item})
    return output


def init(root):
    root = Path(root).resolve()
    if (root / ".bank/config.json").exists():
        return {"vault": str(root), "action": "already_initialized"}
    for name in (ui.QUESTION_DIR, ui.KNOWLEDGE_DIR, ui.PERSONAL_DIR, ui.TEXTBOOK_DIR, ui.ASSET_DIR, ui.PAPER_DIR, "待整理", ".bank/records", ".bank/taxonomy"):
        (root / name).mkdir(parents=True, exist_ok=True)
    atomic(root / ".bank/config.json", json_text({"schema": "tizhuang.bank/v1", "created_at": now()}))
    if not (root / "题库入口.md").exists():
        atomic(root / "题库入口.md", "# 我的题庄本地题库\n\n- [[知识库/知识库导航|浏览知识点]]\n- [[教材目录/教材导航|按教材浏览章节]]\n- 打开 **题目库** 查看题目、答案与解析。\n- 打开 **试卷** 查看打印稿和教师稿。\n- 自己的教学笔记放在 **知识库 → 我的教学笔记**。\n\n题目可以在 Obsidian 编辑，保留题目编号和正文标记。检索和组卷指令在 Agent 中发送，不需要安装额外插件。\n")
    return {"vault": str(root), "action": "initialized"}


def tree_download(bank, args):
    if args.file:
        raw = read_json(args.file)
        if isinstance(raw, dict) and (raw.get("subject_id", args.subject) != args.subject or raw.get("phase_id", args.phase) != args.phase):
            raise ValueError("离线知识树的学科/学段不一致")
        nodes = raw.get("nodes") if isinstance(raw, dict) else raw
        source = raw.get("source", "local-import") if isinstance(raw, dict) else "local-import"
    else:
        if not args.api.startswith("https://"):
            raise ValueError("网站接口必须使用 HTTPS")
        source = args.api.rstrip("/") + f"/v1/meta/knowledge-points?subject_id={args.subject}&phase_id={args.phase}&limit=5000"
        req = urllib.request.Request(source, headers={"User-Agent": "TizhuangLocalBank/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read(10_000_001)
        if len(data) > 10_000_000:
            raise ValueError("知识树响应过大")
        nodes = json.loads(data)
        if len(nodes) >= 5000:
            raise ValueError("知识树达到接口上限，完整性无法确认；停止导入")
    tree = validate_tree(nodes)
    scope = f"{args.subject}-{args.phase}"
    package = {"schema": "tizhuang.taxonomy/v1", "subject_id": args.subject, "phase_id": args.phase, "source": source, "downloaded_at": now(), "nodes": nodes}
    atomic(bank.root / ".bank/taxonomy" / f"{scope}.json", json_text(package))
    mapping, paths, base = ui.assign_paths(bank.root, nodes, args.subject, args.phase)
    atomic(bank.root / ".bank/ui-paths.json", json_text(mapping))
    out = bank.root / base
    for key, node in tree.items():
        # Machine files only; Personal is never touched.
        parent = node.get("parent_id")
        children = [(k, v) for k, v in tree.items() if str(v.get("parent_id")) == key]
        meta = {"知识节点编号": key, "精确知识编号": str(node.get("knowledge_id") or ""), "学科编号": args.subject, "学段编号": args.phase, "内容管理": "系统生成"}
        note = "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n# " + node["name"] + "\n\n"
        if str(parent) in tree:
            note += "父知识点：" + ui.link(bank.root, "knowledge", scope, parent, tree[str(parent)]["name"]) + "\n\n"
        note += "\n".join("- " + ui.link(bank.root, "knowledge", scope, k, v["name"]) for k, v in children)
        personal = '教学笔记' if ui.modern(bank.root) else ui.PERSONAL_DIR
        note += f"\n\n个人笔记：[[{personal}/{ui.name(node['name'])} · {scope}|我的教学笔记]]\n"
        atomic(bank.root / paths[key], note)
    roots = [(key, v) for key, v in tree.items() if str(v.get("parent_id")) not in tree]
    atomic(out / "知识树.md", f"# {ui.scope_name(bank.root, args.subject, args.phase)}知识树\n\n共 {len(tree)} 个知识点。点击分类逐级浏览；自己的说明放在“我的教学笔记”。\n\n" + "\n".join("- " + ui.link(bank.root, "knowledge", scope, key, v["name"]) for key, v in roots))
    write_navigation(bank)
    return {"nodes": len(tree), "scope": scope, "path": str(out)}


def public_metadata(route):
    req = urllib.request.Request(DEFAULT_API + "/v1/meta/" + route, headers={"User-Agent": "TizhuangLocalBank/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read(10_000_001)
    if len(data) > 10_000_000:
        raise ValueError("元数据响应超过 10MB")
    return json.loads(data)


def write_navigation(bank):
    mapping = ui.mappings(bank.root)
    knowledge = "# 知识库导航\n\n点击学科进入知识树，按分类浏览：\n\n"
    textbooks = "# 教材导航\n\n不同教材版本分别保存，请选择实际使用的版本：\n\n"
    for scope, nodes in mapping["knowledge"].items():
        subject, phase = scope.split("-")
        base = '资料/知识目录' if ui.modern(bank.root) else ui.KNOWLEDGE_DIR
        path = base + '/' + ui.scope_name(bank.root, subject, phase) + '/知识树'
        knowledge += f"- [[{path}|{ui.scope_name(bank.root, subject, phase)}]]\n"
    for scope, nodes in mapping["chapters"].items():
        subject, phase, edition = scope.split("-")
        base = '资料/教材目录' if ui.modern(bank.root) else ui.TEXTBOOK_DIR
        path = base + '/' + ui.scope_name(bank.root, subject, phase, edition) + '/教材目录'
        textbooks += f"- [[{path}|{ui.scope_name(bank.root, subject, phase, edition)}]]\n"
    atomic(bank.root / ('资料/知识目录/知识库导航.md' if ui.modern(bank.root) else '知识库/知识库导航.md'), knowledge)
    atomic(bank.root / ('资料/教材目录/教材导航.md' if ui.modern(bank.root) else '教材目录/教材导航.md'), textbooks)


def write_question_navigation(bank, questions):
    if ui.modern(bank.root):
        from teacher_library import dashboard
        return dashboard(bank, questions)
    paths = {}
    for path in (bank.root / ui.QUESTION_DIR).rglob("*.md"):
        paths[read_note(path)["id"]] = path
    text = f"# 我的题目库\n\n目前共 **{len(questions)} 道题**。点击题目名称查看正文。\n\n"
    for kind, label in (("website", "网站题目"), ("local", "自编与演示题"), ("ai", "AI 生成的草稿"), ("other", "其他导入题")):
        group = [q for q in questions if (q["source"].get("kind", "local") == kind or (kind == "other" and q["source"].get("kind", "local") not in ("website", "local", "ai")))]
        if not group:
            continue
        text += f"## {label}\n\n"
        for q in group:
            path = paths[q["id"]].relative_to(bank.root).with_suffix("").as_posix()
            status = "已核对" if q["status"] == "reviewed" else "待核对"
            text += f"- [[{path}|{q['title']}]] · {q['type']} · {status}\n"
        text += "\n"
    text += "网站知识树只包含知识目录，不会自动下载所有题目。需要更多题目时，在 Agent 中指定学科、知识点和数量即可导入。\n"
    atomic(bank.root / "题目导航.md", text)
    entry = bank.root / "题库入口.md"
    if entry.exists():
        original = entry.read_text(encoding="utf-8")
        updated = original.replace("- **题目库**：", "- [[题目导航|打开题目库]]：").replace("- 打开 **题目库** 查看题目、答案与解析。", "- [[题目导航|打开题目库]]：题目、答案与解析。")
        if updated != original:
            atomic(entry, updated)


def refresh_catalog(root, subject, phase):
    result = ui.labels(root)
    for key, route in (("subjects", "subjects"), ("phases", "phases"), ("editions", f"editions?subject_id={subject}&phase_id={phase}")):
        result[key].update({str(v["id"]): v["name"] for v in public_metadata(route)})
    atomic(Path(root) / ".bank/catalog/names.json", json_text(result))
    return result


def migrate_cn(root, catalog_file=None):
    root = Path(root).resolve()
    if not (root / ".bank/config.json").exists():
        raise ValueError("目录不是已初始化的题库")
    if not (root / "Questions").exists():
        return {"action": "already_chinese", "vault": str(root)}
    moves = [("Questions", ui.QUESTION_DIR), ("Assets", ui.ASSET_DIR), ("Papers", ui.PAPER_DIR), ("Inbox", "待整理"), ("Knowledge/Personal", ui.PERSONAL_DIR)]
    for old, new in moves:
        if (root / old).exists() and (root / new).exists() and any((root / new).iterdir()):
            raise ValueError(f"中英文目录均有内容，停止迁移避免混合: {new}")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    backup = root.parent / f"题库中文迁移备份-{stamp}.zip"
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
    if catalog_file:
        names = read_json(catalog_file)
        if not all(isinstance(names.get(key), dict) for key in ("subjects", "phases", "editions")):
            raise ValueError("中文名称目录无效")
        atomic(root / ".bank/catalog/names.json", json_text(names))
    questions = [(path, read_note(path), path.read_text(encoding="utf-8-sig")) for path in (root / "Questions").glob("*.md")]
    legacy = root / ".bank/legacy-layout" / stamp
    for old in ("Questions", "Knowledge/Standard", "Textbooks"):
        source = root / old
        if source.exists():
            target = legacy / old
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
    for old, new in moves[1:]:
        source, target = root / old, root / new
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.rmdir()  # Only an already-verified empty folder.
            source.rename(target)
    (root / ui.QUESTION_DIR).mkdir(exist_ok=True)
    bank = Bank(root)
    pathmap = {}
    for file in (root / ".bank/taxonomy").glob("*.json"):
        raw = read_json(file)
        subject, phase = raw["subject_id"], raw["phase_id"]
        tree_download(bank, SimpleNamespace(subject=subject, phase=phase, file=file))
        scope = f"{subject}-{phase}"
        for key, path in ui.mappings(root)["knowledge"][scope].items():
            pathmap[f"Knowledge/Standard/{scope}/{key}"] = path[:-3]
        pathmap[f"Knowledge/Standard/{scope}/知识树"] = (Path(ui.KNOWLEDGE_DIR) / ui.scope_name(root, subject, phase) / "知识树").as_posix()
    for file in (root / ".bank/textbooks").glob("*.json"):
        raw = read_json(file)
        subject, phase, edition = raw["subject_id"], raw["phase_id"], raw["edition_id"]
        textbook_download(bank, SimpleNamespace(subject=subject, phase=phase, edition=edition, file=file))
        scope = f"{subject}-{phase}-{edition}"
        for key, path in ui.mappings(root)["chapters"][scope].items():
            pathmap[f"Textbooks/{scope}/{key}"] = path[:-3]
    for old, q, text in questions:
        target = ui.question_path(root, q)
        pathmap[f"Questions/{old.stem}"] = target.relative_to(root).with_suffix("").as_posix()
        localized_head = note_text(q, root).split("---\n", 2)[1]
        text = re.sub(r"\A---\r?\n.*?\r?\n---\r?\n", "---\n" + localized_head + "---\n", text, count=1, flags=re.S)
        atomic(target, text)
    def fix_links(text):
        def replace(match):
            oldpath, label = match[1], match[2]
            newpath = pathmap.get(oldpath, oldpath.replace("Knowledge/Personal/", ui.PERSONAL_DIR + "/"))
            if label and re.match(r"(?:知识节点|教材章节) \d+$", label):
                label = Path(newpath).name
            return "[[" + newpath + ("|" + label if label else "") + "]]"
        return re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", replace, text).replace("../Assets/", "../附件/")
    for path in list((root / ui.QUESTION_DIR).glob("*.md")) + list((root / ui.PERSONAL_DIR).rglob("*.md")) + list((root / ui.PAPER_DIR).rglob("*.md")):
        atomic(path, fix_links(path.read_text(encoding="utf-8-sig")))
    for paper_dir in (root / ui.PAPER_DIR).iterdir():
        if not paper_dir.is_dir():
            continue
        for old, new in (("student", "打印稿"), ("teacher", "教师稿")):
            role = paper_dir / old
            if role.exists():
                role.rename(paper_dir / new)
                role = paper_dir / new
                if (role / "Assets").exists():
                    (role / "Assets").rename(role / ui.ASSET_DIR)
                if (role / "index.html").exists():
                    (role / "index.html").rename(role / "试卷.html")
                    atomic(role / "试卷.html", (role / "试卷.html").read_text(encoding="utf-8").replace("Assets/", "附件/"))
        note = paper_dir / "试卷.md"
        if note.exists():
            atomic(note, note.read_text(encoding="utf-8").replace("student/index.html", "打印稿/试卷.html").replace("teacher/index.html", "教师稿/试卷.html").replace("学生版", "无答案打印稿").replace("教师版", "含解析教师稿"))
    config = read_json(root / ".bank/config.json")
    config["ui_layout"] = "zh-CN/v1"
    atomic(root / ".bank/config.json", json_text(config))
    if (root / "题库入口.md").exists():
        (root / "题库入口.md").rename(legacy / "原题库入口.md")
    init(root)  # The existing config means init is idempotent; write entry below.
    atomic(root / "题库入口.md", "# 我的题庄本地题库\n\n- [[知识库/知识库导航|浏览知识点]]\n- [[教材目录/教材导航|按教材浏览章节]]\n- **题目库**：题目、答案和解析。\n- **试卷**：无答案打印稿和教师参考稿。\n- **知识库 → 我的教学笔记**：自己的教学资料。\n\n这里是本地资料库，检索、存题和组卷指令请在 Agent 中发送。\n")
    old_knowledge = root / "Knowledge"
    if old_knowledge.exists() and not any(old_knowledge.iterdir()):
        old_knowledge.rmdir()
    bank.questions()
    return {"action": "migrated", "vault": str(root), "questions": len(questions), "backup": str(backup)}


def textbook_download(bank, args):
    route = f"chapters?subject_id={args.subject}&phase_id={args.phase}&edition_id={args.edition}&limit=1000"
    raw = read_json(args.file) if args.file else public_metadata(route)
    nodes = raw.get("nodes") if isinstance(raw, dict) else raw
    if not args.file and len(nodes) >= 1000:
        raise ValueError("教材章节达到接口上限，完整性无法确认，停止导入")
    chapters = validate_tree(nodes)
    for node in nodes:
        if any(str(node.get(field)) != str(getattr(args, arg)) for arg, field in (("subject", "subject_id"), ("phase", "phase_id"), ("edition", "edition_id"))):
            raise ValueError("章节元数据包含其他学科、学段或教材版本")
    scope = f"{args.subject}-{args.phase}-{args.edition}"
    package = {"schema": "tizhuang.textbook/v1", "subject_id": args.subject, "phase_id": args.phase, "edition_id": args.edition, "downloaded_at": now(), "nodes": nodes}
    atomic(bank.root / ".bank/textbooks" / f"{scope}.json", json_text(package))
    mapping, paths, base = ui.assign_paths(bank.root, nodes, args.subject, args.phase, args.edition)
    atomic(bank.root / ".bank/ui-paths.json", json_text(mapping))
    out = bank.root / base
    for key, node in chapters.items():
        meta = {"章节编号": key, "学科编号": args.subject, "学段编号": args.phase, "教材版本编号": args.edition, "年级编号": node.get("grade_id"), "内容管理": "系统生成"}
        text = "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n# " + node["name"] + "\n\n"
        parent = str(node.get("parent_id"))
        if parent in chapters:
            text += "父章节：" + ui.link(bank.root, "chapters", scope, parent, chapters[parent]["name"]) + "\n\n"
        text += "\n".join("- " + ui.link(bank.root, "chapters", scope, k, v["name"]) for k, v in chapters.items() if str(v.get("parent_id")) == key)
        atomic(bank.root / paths[key], text)
    roots = [(k, v) for k, v in chapters.items() if str(v.get("parent_id")) not in chapters]
    atomic(out / "教材目录.md", f"# {ui.scope_name(bank.root, args.subject, args.phase, args.edition)}\n\n共 {len(chapters)} 个章节，与通用知识树分别保存。\n\n" + "\n".join("- " + ui.link(bank.root, "chapters", scope, k, v["name"]) for k, v in roots))
    write_navigation(bank)
    return {"scope": scope, "chapters": len(chapters), "grades": sorted({str(v.get('grade_id')) for v in nodes}), "path": str(out)}


def get_ids(bank, ids):
    all_q = {q["id"]: q for q in bank.questions()}
    if len(ids) != len(set(ids)):
        raise ValueError("题目 ID 重复")
    missing = [v for v in ids if v not in all_q]
    if missing:
        raise ValueError(f"题目不存在: {missing}")
    return [all_q[v] for v in ids]


def media_references(q):
    text = "\n".join(q[k] for k in ("content", "answer", "analysis"))
    return re.findall(r'<img\b[^>]*\bsrc=[\"\']([^\"\']+)', text, re.I) + re.findall(r"!\[[^\]]*\]\(([^\s)]+)", text)


def verify_media(bank, q):
    assets = {a["path"]: a for a in q["assets"]}
    for ref in media_references(q):
        if ref not in assets:
            raise ValueError(f"题目图片未本地化或未登记: {ref}；请先下载或导入附件")
        if digest(ui.asset_path(bank.root, ref).read_bytes()) != assets[ref]["sha256"]:
            raise ValueError("题目图片文件校验失败")


def download_images(q, base):
    # Opt-in only. No cookies, account tokens, or licence headers are sent.
    for ref in dict.fromkeys(media_references(q)):
        if not ref.startswith("https://"):
            if ref.startswith(("http://", "//", "data:")):
                raise ValueError("图片下载只支持 HTTPS；请手动导入其他图片")
            continue
        host = urlsplit(ref).hostname or ""
        if host in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("不允许下载本机地址图片")
        req = urllib.request.Request(ref, headers={"User-Agent": "TizhuangLocalBank/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            mime = response.headers.get_content_type()
            if not response.url.startswith("https://"):
                raise ValueError("图片重定向到非 HTTPS")
            data = response.read(10_000_001)
        extensions = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
        if mime not in extensions or len(data) > 10_000_000:
            raise ValueError("图片格式不支持或超过 10MB")
        rel = f"Assets/{digest(data)}{extensions[mime]}"
        atomic(base / rel, data)
        for key in ("content", "answer", "analysis"):
            q[key] = q[key].replace(ref, rel)
        q.setdefault("assets", []).append({"path": rel, "sha256": digest(data)})


def export_package(bank, args):
    selected = get_ids(bank, args.ids)
    included_assets = {}
    for q in selected:
        if not args.include_solutions:
            q["answer"] = q["analysis"] = ""
        verify_media(bank, q)
        # Export only assets actually referenced in the chosen visible sections.
        text = q["content"] + q["answer"] + q["analysis"]
        q["assets"] = [v for v in q["assets"] if v["path"] in text]
        for asset in q["assets"]:
            data = ui.asset_path(bank.root, asset["path"]).read_bytes()
            if digest(data) != asset["sha256"]:
                raise ValueError("本地附件发生改变")
            included_assets[asset["path"]] = data
    package = {"schema": PACKAGE, "includes_solutions": bool(args.include_solutions), "questions": selected}
    target = Path(args.output).resolve()
    if target.exists():
        raise ValueError("输出文件已存在，不覆盖")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        staged = Path(work) / "package.zip"
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("questions.json", json_text(package))
            for path, data in included_assets.items():
                z.writestr(path, data)
        atomic(target, staged.read_bytes())
    return {"path": str(target), "questions": len(selected), "includes_solutions": bool(args.include_solutions)}


def import_package(bank, path):
    with tempfile.TemporaryDirectory() as work:
        base = Path(work)
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if sum(v.file_size for v in infos) > 100_000_000 or len(infos) > 1000:
                raise ValueError("题目包超出 100MB/1000 文件限制")
            names = set()
            for info in infos:
                name = safe_relative(info.filename)
                if name in names or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("题目包含重复、目录或符号链接条目")
                if name != "questions.json" and not name.startswith("Assets/"):
                    raise ValueError("题目包含不允许的文件")
                names.add(name)
                atomic(inside(base, name), z.read(info))
        package = read_json(base / "questions.json")
        if package.get("schema") != PACKAGE:
            raise ValueError("不支持的题目包协议")
        questions = package.get("questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError("题目包为空")
        # Preflight attachment hashes for all records before creating notes.
        for q in questions:
            normalize(q)
            for asset in q.get("assets", []):
                if digest(inside(base, asset["path"]).read_bytes()) != asset.get("sha256"):
                    raise ValueError("题目包附件校验失败")
        return [bank.save(q, base) for q in questions]


def paper(bank, args):
    from paper_builder import build
    return build(bank, args)


def filters(parser):
    for name in ("subject", "phase", "grade", "edition"):
        parser.add_argument("--" + name, type=int)
    for name in ("type", "tag", "knowledge", "chapter", "query"):
        parser.add_argument("--" + name)
    parser.add_argument("--status", choices=["draft", "reviewed"])
    parser.add_argument("--unused", action="store_true")


def status(bank):
    """One read-only health snapshot so an Agent can decide the next step without guessing."""
    rows = bank.questions()
    total = len(rows)
    draft = sum(q["status"] != "reviewed" for q in rows)
    unclassified = sum(not q["knowledge_tree_ids"] and not q["chapter_ids"] for q in rows)
    no_answer = sum(not str(q.get("answer", "")).strip() for q in rows)
    trees = sorted(p.stem for p in (bank.root / ".bank/taxonomy").glob("*.json")) if (bank.root / ".bank/taxonomy").is_dir() else []
    papers = len([p for p in (bank.root / ui.PAPER_DIR).glob("*/manifest.json")]) if (bank.root / ui.PAPER_DIR).is_dir() else 0
    steps = []
    if not trees:
        steps.append("还没有知识树：先 tree --subject <学科> --phase <学段> 下载，分类和按考点找题都依赖它。")
    if not total:
        steps.append("题库还是空的：导入 PDF（pdf-prepare）或存入题目 JSON（import）。")
    if unclassified and trees:
        steps.append(f"{unclassified} 道题尚未关联知识点：先 auto-classify，剩余的由 Agent 阅读后 classify。")
    if draft:
        steps.append(f"{draft} 道题待老师核对：核对后才能正式组卷。")
    if total and not draft and not papers:
        steps.append("题目都已核对，可以组卷。")
    return {"vault": str(bank.root), "questions": total, "draft": draft, "reviewed": total - draft,
            "unclassified": unclassified, "without_answer": no_answer, "knowledge_trees": trees,
            "papers": papers, "python": sys.version.split()[0], "next_steps": steps}


def show(bank, args):
    """Full records (with the hash classify needs) for the requested IDs; read-only."""
    rows = []
    for q in get_ids(bank, args.ids):
        rows.append({"id": q["id"], "title": q["title"], "type": q.get("type"), "status": q["status"], "score": q.get("score"),
                     "subject_id": q.get("subject_id"), "phase_id": q.get("phase_id"), "edition_id": q.get("edition_id"),
                     "chapter_ids": q["chapter_ids"], "knowledge_tree_ids": q["knowledge_tree_ids"], "tags": q["tags"],
                     "path": bank.note_paths[q["id"]].relative_to(bank.root).as_posix(),
                     "content": q["content"], "answer": q["answer"], "analysis": q["analysis"],
                     "content_sha256": digest("\n".join(q[k] for k in ("content", "answer", "analysis")).encode("utf-8"))})
    return rows


HINTS = (
    ("题库未初始化", "先运行 init，或确认 --vault 指向正确的题库目录。"),
    ("旧版英文目录", "先运行 migrate-cn；原文件不会被覆盖。"),
    ("知识节点不存在", "先用 tree 下载该学科学段知识树，再用 tree-search 找真实节点编号。"),
    ("题目内容已改变", "用 show --ids 重新读取题目，取新的 content_sha256 并重新判断分类。"),
    ("题目不存在", "用 search 或 status 确认题目 ID；ID 来自本地题库而不是网站题号。"),
    ("缺题", "按 --plan 的提示放宽题量或补充题目；工具不会自动扩大范围。"),
    ("尚未核对", "请老师逐题核对后再用 review --confirm；不要替老师确认。"),
    ("HTTPS", "该操作需要联网；离线时可用 --file 提供本地 JSON。"),
    ("timed out", "网络超时，稍后重试；已保存的内容不受影响。"),
)


def hint_for(message):
    return next((hint for key, hint in HINTS if key in message), "")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="题庄独立本地题库：Markdown 真源，SQLite 可重建索引")
    parser.add_argument("--vault", required=True, help="Obsidian vault / 普通题库目录")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("status", help="只读体检（不改任何文件）：题量、待核对、待分类、知识树与下一步建议")
    show_cmd = sub.add_parser("show", help="读取题目完整内容及 classify 所需的 content_sha256")
    show_cmd.add_argument("--ids", nargs="+", required=True)
    sub.add_parser('organize', help='备份后整理教师目录、标题与原生标签')
    sub.add_parser('dashboard', help='更新题库首页')
    classification = sub.add_parser('classify', help='按 Agent 核对的真实知识节点批量分类，保留正文和教材')
    classification.add_argument('--file', required=True, help='tizhuang.classification/v1 JSON')
    classification.add_argument('--plan', action='store_true', help='验证并预览，不修改题目')
    automatic = sub.add_parser('auto-classify', help='为未关联题目精确匹配考点标签，其余交给 Agent')
    automatic.add_argument('--batch')
    automatic.add_argument('--ids', nargs='+')
    sub.add_parser('repair-papers', help='备份并修复历史打印稿入口')
    pdf_prepare = sub.add_parser('pdf-prepare', help='登记 PDF、渲染原页并识别单栏题号')
    pdf_prepare.add_argument('--file', required=True)
    for field in ('subject', 'phase', 'edition'):
        pdf_prepare.add_argument('--' + field, type=int)
    pdf_prepare.add_argument('--chapter', nargs='+')
    pdf_commit = sub.add_parser('pdf-import', help='从 PDF 分题清单导入可编辑草稿')
    pdf_commit.add_argument('--batch', required=True)
    pdf_commit.add_argument('--segmentation', help='Agent 核对后的分题 JSON；扫描或双栏 PDF 必需')
    pdf_commit.add_argument('--image-draft', action='store_true', help='明确使用旧式图片草稿（默认要求可编辑正文）')
    pdf_commit.add_argument('--upgrade-to-editable', action='store_true', help='备份后将同批次未编辑的图片草稿升级，保留原 ID 和老师批注')
    migration = sub.add_parser("migrate-cn")
    migration.add_argument("--catalog-labels")
    catalog = sub.add_parser("catalog")
    catalog.add_argument("--subject", type=int, required=True)
    catalog.add_argument("--phase", type=int, required=True)
    tree = sub.add_parser("tree")
    tree.add_argument("--subject", type=int, required=True)
    tree.add_argument("--phase", type=int, required=True)
    tree.add_argument("--api", default=DEFAULT_API)
    tree.add_argument("--file", help="离线知识树 JSON")
    tree_search = sub.add_parser("tree-search")
    tree_search.add_argument("--subject", type=int, required=True)
    tree_search.add_argument("--phase", type=int, required=True)
    tree_search.add_argument("--query", required=True)
    editions = sub.add_parser("editions")
    editions.add_argument("--subject", type=int, required=True)
    editions.add_argument("--phase", type=int, required=True)
    textbooks = sub.add_parser("chapters")
    for name in ("subject", "phase", "edition"):
        textbooks.add_argument("--" + name, type=int, required=True)
    textbooks.add_argument("--file")
    chapter_search = sub.add_parser("chapter-search")
    for name in ("subject", "phase", "edition"):
        chapter_search.add_argument("--" + name, type=int, required=True)
    chapter_search.add_argument("--query", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("--file", required=True)
    imp.add_argument("--website", action="store_true", help="适配题庄现有 skill 返回的原始 items JSON")
    imp.add_argument("--download-images", action="store_true", help="显式下载输入正文引用的 HTTPS 图片")
    for name in ("subject", "phase", "edition"):
        imp.add_argument("--" + name, type=int)
    imp.add_argument("--chapter", nargs="+", help="教师确认的教材章节关联；不按知识名称自动推断")
    search = sub.add_parser("search")
    filters(search)
    search.add_argument("--limit", type=int, help="最多返回条数，题库很大时使用")
    review = sub.add_parser("review")
    review.add_argument("--ids", nargs="+", required=True)
    review.add_argument("--confirm", action="store_true", required=True, help="已人工核对题干、答案和图片")
    exp = sub.add_parser("export")
    exp.add_argument("--ids", nargs="+", required=True)
    exp.add_argument("--output", required=True)
    exp.add_argument("--include-solutions", action="store_true")
    paper_cmd = sub.add_parser("paper")
    filters(paper_cmd)
    paper_cmd.set_defaults(status="reviewed")
    paper_cmd.add_argument("--ids", nargs="+")
    paper_cmd.add_argument("--count", type=int)
    paper_cmd.add_argument("--title", default="本地练习卷")
    paper_cmd.add_argument("--plan", action="store_true")
    paper_cmd.add_argument("--basket", help="本地组卷篮 JSON，按题序及本卷分值生成")
    paper_cmd.add_argument("--duration", type=int)
    paper_cmd.add_argument("--confirm-reviewed", action="store_true", help="老师已明确逐题核对当前组卷篮")
    args = parser.parse_args()
    if args.command == "init":
        result = init(args.vault)
    elif args.command == "migrate-cn":
        result = migrate_cn(args.vault, args.catalog_labels)
    else:
        bank = Bank(args.vault)
        # status / show / search only read: leave the index and navigation notes untouched (use dashboard to refresh them).
        bank.readonly = args.command in ("status", "show", "search")
        if args.command == 'organize':
            from teacher_library import organize
            result = organize(bank)
        elif args.command == 'dashboard':
            from teacher_library import dashboard
            result = dashboard(bank, bank.questions())
        elif args.command == 'auto-classify':
            from auto_classify import run
            result = run(bank, args)
        elif args.command == 'repair-papers':
            from paper_links import repair
            result = repair(bank)
        elif args.command == 'classify':
            from teacher_library import classify
            result = classify(bank, args)
        elif args.command in ('pdf-prepare', 'pdf-import'):
            from pdf_import import prepare, commit
            result = prepare(bank, args) if args.command == 'pdf-prepare' else commit(bank, args)
        elif args.command == "tree":
            result = tree_download(bank, args)
        elif args.command == "catalog":
            result = refresh_catalog(bank.root, args.subject, args.phase)
        elif args.command == "tree-search":
            result = [node for node in bank.taxonomy(args.subject, args.phase).values() if args.query.casefold() in node["name"].casefold()]
        elif args.command == "editions":
            result = public_metadata(f"editions?subject_id={args.subject}&phase_id={args.phase}")
            atomic(bank.root / ".bank/catalog" / f"editions-{args.subject}-{args.phase}.json", json_text(result))
        elif args.command == "chapters":
            result = textbook_download(bank, args)
        elif args.command == "chapter-search":
            result = [node for node in bank.chapters(args.subject, args.phase, args.edition).values() if args.query.casefold() in node["name"].casefold()]
        elif args.command == "import":
            path = Path(args.file).resolve()
            if path.suffix.lower() == ".zip":
                result = import_package(bank, path)
            else:
                payload = read_json(path)
                if args.website:
                    questions = website_questions(payload)
                elif isinstance(payload, dict) and payload.get("schema") == PACKAGE:
                    questions = payload["questions"]
                else:
                    questions = payload if isinstance(payload, list) else [payload]
                for q in questions:
                    for arg, field in (("subject", "subject_id"), ("phase", "phase_id"), ("edition", "edition_id")):
                        value = getattr(args, arg)
                        if value is not None:
                            if q.get(field) not in (None, value):
                                raise ValueError(f"输入题目 {field} 与指定值不一致")
                            q[field] = value
                    if args.chapter:
                        if q.get("chapter_ids") and set(map(str, q["chapter_ids"])) != set(args.chapter):
                            raise ValueError("输入题目章节与指定值不一致")
                        q["chapter_ids"] = args.chapter
                if args.download_images:
                    with tempfile.TemporaryDirectory() as image_dir:
                        image_base = Path(image_dir)
                        # Copy explicitly supplied local assets as well.
                        for q in questions:
                            for asset in q.get("assets", []):
                                atomic(inside(image_base, asset["path"]), inside(path.parent, asset["path"]).read_bytes())
                            download_images(q, image_base)
                        result = [bank.save(q, image_base) for q in questions]
                else:
                    result = [bank.save(q, path.parent) for q in questions]
        elif args.command == "status":
            result = status(bank)
        elif args.command == "show":
            result = show(bank, args)
        elif args.command == "search":
            found = bank.select(args)
            if args.limit is not None:
                if args.limit < 1:
                    raise ValueError("--limit 必须是正整数")
                found = found[:args.limit]
            result = [{k: q.get(k) for k in ("id", "title", "type", "status", "subject_id", "phase_id", "grade_id", "edition_id", "chapter_ids", "knowledge_tree_ids", "tags")} for q in found]
        elif args.command == "review":
            result = []
            for q in get_ids(bank, args.ids):
                verify_media(bank, q)
                path = bank.note_paths[q["id"]]
                atomic(bank.root / ".bank/backups" / f'{q["id"]}-{uuid.uuid4().hex}.md', path.read_bytes())
                q["status"] = "reviewed"
                q["updated_at"] = now()
                original = path.read_text(encoding="utf-8-sig")
                header = note_text(q, bank.root).split("---\n", 2)[1]
                updated = re.sub(r"\A---\r?\n.*?\r?\n---\r?\n", "---\n" + header + "---\n", original, count=1, flags=re.S)
                atomic(path, updated)
                result.append({"id": q["id"], "status": "reviewed"})
        elif args.command == "export":
            result = export_package(bank, args)
        else:
            result = paper(bank, args)
    print(json_text({"ok": True, "result": result}), end="")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, yaml.YAMLError, zipfile.BadZipFile) as exc:
        message = str(exc) or exc.__class__.__name__
        print(json_text({"ok": False, "error": message, "hint": hint_for(message)}), end="")
        sys.exit(1)
    except Exception as exc:  # never leak a traceback to a teacher-facing agent
        print(json_text({"ok": False, "kind": "unexpected", "error": f"{exc.__class__.__name__}: {exc}",
                         "hint": "这是未预期的错误：不要重试写入操作，先 status 检查题库，并把本消息反馈给开发者。"}), end="")
        sys.exit(2)
