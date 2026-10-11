import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import subprocess
import sys
import unittest
import zipfile

SCRIPT = Path(__file__).parents[2] / "skills/tizhuang-local-bank/scripts/local_bank.py"
spec = importlib.util.spec_from_file_location("local_bank", SCRIPT)
lb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lb)


class BankTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        lb.init(self.root / "vault")
        self.bank = lb.Bank(self.root / "vault")
        self.tree = [{"id": 10, "name": "函数", "parent_id": None, "knowledge_id": 80}, {"id": 11, "name": "一次函数", "parent_id": 10, "knowledge_id": 81}]
        lb.atomic(self.root / "tree.json", lb.json_text(self.tree))
        lb.tree_download(self.bank, SimpleNamespace(subject=2, phase=2, file=self.root / "tree.json"))

    def tearDown(self):
        self.tmp.cleanup()

    def q(self, **values):
        q = {"id": "test-1", "title": "一次函数测试题", "content": "测试样例：求一次函数的值。", "answer": "SECRET_ANSWER", "analysis": "SECRET_ANALYSIS", "subject_id": 2, "phase_id": 2, "knowledge_tree_ids": ["11"], "knowledge_ids": ["81"], "tags": ["样例"], "status": "reviewed"}
        q.update(values)
        return q

    def args(self, **values):
        args = dict(subject=None, phase=None, grade=None, edition=None, knowledge=None, type=None, tag=None, query=None, status=None, unused=False, ids=None, count=None, title="测试卷", plan=False)
        args.update(values)
        return SimpleNamespace(**args)

    def note(self, qid="test-1"):
        self.bank.questions()
        return self.bank.note_paths[qid]

    def test_dedup_and_source_conflict(self):
        q = self.q(source={"kind": "website", "provider": "tizhuang", "external_id": "100"})
        self.assertEqual(self.bank.save(q)["action"], "created")
        self.assertEqual(self.bank.save(q)["action"], "duplicate")
        with self.assertRaisesRegex(ValueError, "正文不同"):
            self.bank.save({**q, "id": "test-2", "content": "changed"})

    def test_obsidian_edits_and_index_rebuild(self):
        self.bank.save(self.q())
        path = self.note()
        lb.atomic(path, path.read_text(encoding="utf-8").replace("求一次函数的值", "求三角形面积"))
        self.assertEqual(len(self.bank.select(self.args(query="三角形"))), 1)
        (self.bank.root / ".bank/index.sqlite3").unlink()
        self.assertEqual(len(self.bank.select(self.args(query="三角形"))), 1)

    def test_filters_preserve_subject_and_tree_scope(self):
        self.bank.save(self.q())
        self.assertEqual(len(self.bank.select(self.args(subject=2, phase=2, knowledge="10"))), 1)
        self.assertEqual(self.bank.select(self.args(subject=3)), [])
        self.assertEqual(self.bank.select(self.args(grade=8)), [])
        with self.assertRaises(ValueError):
            self.bank.select(self.args(subject=2, phase=2, knowledge="999"))

    def test_tree_validation_and_personal_notes_preserved(self):
        for bad in ([self.tree[1]], self.tree + [self.tree[0]], [{"id": "../bad", "name": "bad"}], [{"id": 1, "name": "a", "parent_id": 2}, {"id": 2, "name": "b", "parent_id": 1}]):
            with self.assertRaises(ValueError):
                lb.validate_tree(bad)
        personal = self.bank.root / "知识库/我的教学笔记/2-2-11.md"
        lb.atomic(personal, "MY_NOTE")
        lb.tree_download(self.bank, SimpleNamespace(subject=2, phase=2, file=self.root / "tree.json"))
        self.assertEqual(personal.read_text(), "MY_NOTE")

    def test_textbook_isolation_and_chapter_descendants(self):
        nodes = [{"id": 100, "name": "第十九章", "parent_id": 0, "subject_id": 2, "phase_id": 2, "edition_id": 59, "grade_id": 208}, {"id": 101, "name": "一次函数", "parent_id": 100, "subject_id": 2, "phase_id": 2, "edition_id": 59, "grade_id": 208}]
        source = self.root / "chapters.json"
        lb.atomic(source, lb.json_text(nodes))
        lb.textbook_download(self.bank, SimpleNamespace(subject=2, phase=2, edition=59, file=source))
        self.bank.save(self.q(edition_id=59, chapter_ids=["101"]))
        self.bank.save(self.q(id="test-2", edition_id=142))
        selected = self.bank.select(self.args(subject=2, phase=2, edition=59, chapter="100"))
        self.assertEqual([v["id"] for v in selected], ["test-1"])
        self.assertEqual([v["id"] for v in self.bank.select(self.args(edition=142))], ["test-2"])
        with self.assertRaisesRegex(ValueError, "版本"):
            lb.textbook_download(self.bank, SimpleNamespace(subject=2, phase=2, edition=142, file=source))
        with self.assertRaisesRegex(ValueError, "教材版本"):
            self.bank.save(self.q(id="test-3", edition_id=59, chapter_ids=["999"]))

    def test_parent_questions_and_student_solution_exclusion(self):
        raw = {"items": [{"id": 999, "title_html": "母题", "options_html": {"B": "第二项", "A": "第一项"}, "answer_html": "PARENT_SECRET", "analysis_html": "ANALYSIS_SECRET", "subquestions": [{"title_html": "子题", "answer_html": "CHILD_SECRET", "analysis_html": "CHILD_ANALYSIS"}]}]}
        q = lb.website_questions(raw)[0]
        q["status"] = "reviewed"
        result = self.bank.save(q)
        result = lb.paper(self.bank, self.args(ids=[result["id"]]))
        student = Path(result["student"]).read_text(encoding="utf-8")
        teacher = Path(result["teacher"]).read_text(encoding="utf-8")
        self.assertIn("子题", student)
        self.assertLess(student.index("第二项"), student.index("第一项"))
        for secret in ("PARENT_SECRET", "ANALYSIS_SECRET", "CHILD_SECRET", "CHILD_ANALYSIS"):
            self.assertNotIn(secret, student)
            self.assertIn(secret, teacher)
        record = lb.read_json(list((self.bank.root / ".bank/records").glob("*.json"))[0])
        self.assertEqual(record["original_payload"], raw["items"][0])

    def test_paper_is_snapshot_and_shortage_creates_nothing(self):
        self.bank.save(self.q())
        with self.assertRaisesRegex(ValueError, "题目不足"):
            lb.paper(self.bank, self.args(count=2, status="reviewed"))
        self.assertEqual(list((self.bank.root / "试卷").iterdir()), [])
        result = lb.paper(self.bank, self.args(ids=["test-1"]))
        path = self.note()
        lb.atomic(path, path.read_text(encoding="utf-8").replace("SECRET_ANSWER", "NEW_ANSWER"))
        self.assertIn("SECRET_ANSWER", Path(result["teacher"]).read_text(encoding="utf-8"))
        self.assertEqual(self.bank.select(self.args(unused=True)), [])

    def test_drafts_cannot_be_explicitly_assembled(self):
        self.bank.save(self.q(status="draft"))
        with self.assertRaisesRegex(ValueError, "reviewed"):
            lb.paper(self.bank, self.args(ids=["test-1"]))

    def test_explicit_ids_do_not_discard_scope_and_zero_count(self):
        self.bank.save(self.q())
        with self.assertRaisesRegex(ValueError, "筛选条件"):
            lb.paper(self.bank, self.args(ids=["test-1"], subject=3))
        with self.assertRaisesRegex(ValueError, "题目不足"):
            lb.paper(self.bank, self.args(count=0))

    def test_bundle_roundtrip_with_assets_and_default_privacy(self):
        source = self.root / "source"
        lb.atomic(source / "image.png", b"fake-test-image")
        lb.atomic(source / "answer.png", b"private-answer-image")
        q = self.q(content="题图 ![题图](image.png)", answer="SECRET_ANSWER ![解图](answer.png)", assets=[{"path": "image.png"}, {"path": "answer.png"}])
        self.bank.save(q, source)
        output = self.root / "packet.zip"
        lb.export_package(self.bank, SimpleNamespace(ids=["test-1"], output=output, include_solutions=False))
        with zipfile.ZipFile(output) as z:
            self.assertEqual(len(z.namelist()), 2)
            payload = z.read("questions.json").decode()
            self.assertNotIn("SECRET_ANSWER", payload)
            self.assertNotIn("SECRET_ANALYSIS", payload)
            self.assertNotIn("original_payload", payload)
        lb.init(self.root / "other")
        other = lb.Bank(self.root / "other")
        lb.tree_download(other, SimpleNamespace(subject=2, phase=2, file=self.root / "tree.json"))
        lb.import_package(other, output)
        imported = other.questions()[0]
        self.assertEqual(imported["answer"], "")
        self.assertTrue(lb.ui.asset_path(other.root, imported["assets"][0]["path"]).exists())
        self.assertIn("../附件/", other.note_paths["test-1"].read_text(encoding="utf-8"))

    def test_zip_traversal_and_hash_failure(self):
        malicious = self.root / "bad.zip"
        with zipfile.ZipFile(malicious, "w") as z:
            z.writestr("../outside.txt", "oops")
        with self.assertRaises(ValueError):
            lb.import_package(self.bank, malicious)
        with zipfile.ZipFile(malicious, "w") as z:
            q = self.q(assets=[{"path": "Assets/1.png", "sha256": "wrong"}])
            z.writestr("questions.json", lb.json_text({"schema": lb.PACKAGE, "questions": [q]}))
            z.writestr("Assets/1.png", "image")
        with self.assertRaisesRegex(ValueError, "校验失败"):
            lb.import_package(self.bank, malicious)
        self.assertEqual(self.bank.questions(), [])

    def test_remote_images_cannot_be_reviewed_or_printed(self):
        self.bank.save(self.q(content='题目 <img src="https://example.com/a.png">'))
        with self.assertRaisesRegex(ValueError, "未本地化"):
            lb.paper(self.bank, self.args(ids=["test-1"]))
        self.assertEqual(list((self.bank.root / "试卷").iterdir()), [])

    def test_chinese_names_and_ids_survive_user_rename(self):
        self.bank.save(self.q())
        path = self.note()
        self.assertIn("一次函数测试题", path.name)
        self.assertNotIn("test-1", path.name)
        text = path.read_text(encoding="utf-8")
        self.assertIn("题目编号: test-1", text)
        self.assertIn("审核状态: 已核对", text)
        self.assertIn("一次函数", text)
        path.rename(path.with_name("老师自己的名称.md"))
        self.assertEqual(self.bank.select(self.args(query="函数"))[0]["id"], "test-1")

    def test_review_keeps_teacher_extra_sections(self):
        self.bank.save(self.q(status="draft"))
        path = self.note()
        lb.atomic(path, path.read_text(encoding="utf-8") + "\n## 我的课后备注\n这段不能丢失。\n")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(self.bank.root), "review", "--ids", "test-1", "--confirm"], capture_output=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("这段不能丢失", path.read_text(encoding="utf-8"))
        self.assertEqual(self.bank.questions()[0]["status"], "reviewed")

    def test_backup_migration_preserves_custom_notes_and_links(self):
        root = self.root / "legacy"
        lb.atomic(root / ".bank/config.json", lb.json_text({"schema": "tizhuang.bank/v1"}))
        lb.atomic(root / ".bank/taxonomy/2-2.json", lb.json_text({"subject_id": 2, "phase_id": 2, "nodes": self.tree}))
        q = lb.normalize(self.q())
        oldtext = lb.note_text(q) + "\n## 老师自己的补充\n\n不能丢失。[[Knowledge/Standard/2-2/11|知识节点 11]]\n"
        lb.atomic(root / "Questions/test-1.md", oldtext)
        lb.atomic(root / "Knowledge/Personal/老师笔记.md", "我的笔记 [[Questions/test-1]]")
        lb.atomic(root / "Papers/p1/试卷.md", "[[Questions/test-1]] [学生版](student/index.html)")
        lb.atomic(root / "Papers/p1/student/index.html", "<p>无答案试卷</p>")
        result = lb.migrate_cn(root)
        self.assertTrue(Path(result["backup"]).exists())
        bank = lb.Bank(root)
        self.assertEqual(len(bank.questions()), 1)
        text = bank.note_paths["test-1"].read_text(encoding="utf-8")
        self.assertIn("不能丢失", text)
        self.assertNotIn("Knowledge/", text)
        self.assertFalse((root / "Questions").exists())
        self.assertTrue((root / "试卷/p1/打印稿/试卷.html").exists())
        self.assertIn("题目库/一次函数测试题", (root / "知识库/我的教学笔记/老师笔记.md").read_text(encoding="utf-8"))
        self.assertEqual(lb.migrate_cn(root)["action"], "already_chinese")

    def test_html_sanitizes_active_content(self):
        text = lb.render('<script>EVIL</script><p onclick="evil()">正常</p><img src="https://remote/a.png"><a href="javascript:evil()">link</a>', "html")
        self.assertNotIn("EVIL", text)
        self.assertNotIn("onclick", text)
        self.assertNotIn("javascript:", text)
        self.assertNotIn("https:", text)
        self.assertIn("正常", text)

    def test_math_is_offline_mathml(self):
        result = lb.render(r"求 $\frac{1}{2}x^2$，并计算 $$\sqrt{9}=3$$。")
        self.assertIn("<math", result)
        self.assertIn("<mfrac>", result)
        self.assertIn("<msqrt>", result)
        self.assertNotIn("<script", result)
        self.assertNotIn("BANKMATHTOKEN", result)


if __name__ == "__main__":
    unittest.main()
