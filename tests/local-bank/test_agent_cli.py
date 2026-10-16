"""Agent-facing CLI contract: status, show -> classify round trip, limit, hints, doctor."""
from pathlib import Path
import hashlib, json, subprocess, sys, tempfile, unittest

SCRIPTS = Path(__file__).parents[2] / 'skills/tizhuang-local-bank/scripts'
sys.path.insert(0, str(SCRIPTS))
import local_bank as lb


def cli(*args, script='local_bank.py'):
    run = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, encoding='utf-8')
    return run.returncode, json.loads(run.stdout)


class AgentCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        lb.init(self.root)
        lb.atomic(self.root / '.bank/taxonomy/2-2.json', lb.json_text({'nodes': [{'id': 11, 'parent_id': 0, 'name': '反比例函数', 'knowledge_id': 200}]}))
        bank = lb.Bank(self.root)
        bank.save({'id': 'a', 'title': '题一', 'subject_id': 2, 'phase_id': 2, 'content': '求面积。', 'answer': '6'})
        bank.save({'id': 'b', 'title': '题二', 'subject_id': 2, 'phase_id': 2, 'content': '另一题。'})

    def tearDown(self):
        self.tmp.cleanup()

    def v(self):
        return ['--vault', str(self.root)]

    def test_status_reports_counts_and_next_steps(self):
        code, out = cli(*self.v(), 'status')
        self.assertEqual(code, 0)
        r = out['result']
        self.assertEqual((r['questions'], r['draft'], r['unclassified'], r['without_answer']), (2, 2, 2, 1))
        self.assertEqual(r['knowledge_trees'], ['2-2'])
        self.assertTrue(any('auto-classify' in s for s in r['next_steps']))

    def test_show_hash_drives_classify_without_manual_hashing(self):
        _, out = cli(*self.v(), 'show', '--ids', 'a', 'b')
        rows = out['result']
        self.assertEqual(rows[0]['content'], '求面积。')
        plan = {'schema': 'tizhuang.classification/v1', 'items': [
            {'id': r['id'], 'knowledge_tree_ids': ['11'], 'reason': '考查反比例函数', 'expected_content_sha256': r['content_sha256']} for r in rows]}
        path = self.root / 'plan.json'
        path.write_text(json.dumps(plan), encoding='utf-8')
        code, out = cli(*self.v(), 'classify', '--file', str(path))
        self.assertEqual(code, 0, out)
        _, status = cli(*self.v(), 'status')
        self.assertEqual(status['result']['unclassified'], 0)

    def test_search_limit_and_validation(self):
        _, out = cli(*self.v(), 'search', '--limit', '1')
        self.assertEqual(len(out['result']), 1)
        code, out = cli(*self.v(), 'search', '--limit', '0')
        self.assertEqual(code, 1)
        self.assertFalse(out['ok'])

    def test_errors_carry_actionable_hint(self):
        code, out = cli(*self.v(), 'show', '--ids', 'missing')
        self.assertEqual(code, 1)
        self.assertIn('search', out['hint'])
        code, out = cli('--vault', str(self.root / 'nowhere'), 'status')
        self.assertEqual(code, 1)
        self.assertIn('init', out['hint'])

    def snapshot(self):
        return {str(p.relative_to(self.root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                for p in sorted(self.root.rglob('*')) if p.is_file()}

    def test_status_show_search_doctor_never_write(self):
        before = self.snapshot()
        index = self.root / '.bank/index.sqlite3'
        if index.exists():
            index.unlink()
            before = self.snapshot()
        cli(*self.v(), 'status')
        cli(*self.v(), 'show', '--ids', 'a')
        cli(*self.v(), 'search', '--query', '面积')
        cli('--vault', str(self.root), script='doctor.py')
        self.assertEqual(before, self.snapshot())

    def test_doctor_fails_when_vault_cannot_be_read(self):
        (self.root / '题目库/损坏.md').write_text('---\nid: [oops\n---\n', encoding='utf-8')
        code, out = cli('--vault', str(self.root), script='doctor.py')
        self.assertEqual(code, 1)
        self.assertFalse(out['ok'])
        self.assertTrue(out['next_steps'])

    def test_fix_command_quotes_paths_with_spaces(self):
        import doctor
        from unittest import mock
        with mock.patch.object(doctor.os, 'name', 'nt'):
            cmd = doctor.pip_command(r'C:\Program Files\Python312\python.exe', r'C:\Users\王 老师\req.txt')
        self.assertEqual(cmd, r'& "C:\Program Files\Python312\python.exe" -m pip install -r "C:\Users\王 老师\req.txt"')
        with mock.patch.object(doctor.os, 'name', 'posix'):
            cmd = doctor.pip_command('/opt/my python/bin/python', '/tmp/a b/req.txt')
        self.assertEqual(cmd, "'/opt/my python/bin/python' -m pip install -r '/tmp/a b/req.txt'")

    def test_doctor_runs_without_vault_and_with_one(self):
        code, out = cli(script='doctor.py')
        self.assertEqual(code, 0)
        self.assertTrue(out['ok'])
        code, out = cli('--vault', str(self.root), script='doctor.py')
        self.assertEqual(out['status']['result']['questions'], 2)


if __name__ == '__main__':
    unittest.main()
