import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('studio_install', Path(__file__).resolve().parents[1] / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'package'
        self.target = self.root / 'skills/tizhuang-studio'
        self.work = self.root / '教师题库'
        self.work.mkdir()
        (self.work / 'studio.sqlite3').write_bytes(b'user questions must survive')
        self.source.mkdir()
        (self.source / 'SKILL.md').write_text('name: tizhuang-studio\nmetadata:\n  version: 1.0.0\n')
        for name in ('README.md', '.gitignore'):
            (self.source / name).write_text(name)
        for folder in ('scripts', 'references', 'assets'):
            (self.source / folder).mkdir()
        (self.source / 'scripts/app.py').write_text('v1')

    def install(self):
        return installer.install_program(self.source, self.target, self.work)

    def test_install_skip_and_upgrade_preserve_data_environment_unknown_files(self):
        self.assertEqual(self.install()['action'], 'install')
        (self.target / '.venv').mkdir()
        (self.target / '.venv/keep').write_text('environment')
        (self.target / 'notes.txt').write_text('user config')
        self.assertEqual(self.install()['action'], 'skip')
        (self.source / 'scripts/app.py').write_text('v2')
        result = self.install()
        self.assertEqual(result['action'], 'update')
        self.assertEqual((Path(result['backup']) / 'scripts/app.py').read_text(), 'v1')
        self.assertEqual((self.target / 'scripts/app.py').read_text(), 'v2')
        self.assertEqual((self.target / '.venv/keep').read_text(), 'environment')
        self.assertEqual((self.target / 'notes.txt').read_text(), 'user config')
        self.assertEqual((self.work / 'studio.sqlite3').read_bytes(), b'user questions must survive')

    def test_reject_other_skill_and_workspace_overlap(self):
        with self.assertRaises(ValueError):
            installer.install_program(self.source, self.root / 'skills/question-bank', self.work)
        with self.assertRaises(ValueError):
            installer.install_program(self.source, self.target, self.target / 'data')
        self.target.mkdir(parents=True)
        (self.target / 'studio.sqlite3').write_text('private data')
        with self.assertRaises(ValueError):
            self.install()

    def test_no_downgrade(self):
        self.install()
        (self.target / 'SKILL.md').write_text('name: tizhuang-studio\nmetadata:\n  version: 2.0.0\n')
        self.assertEqual(self.install()['action'], 'skip-newer')

    def test_only_obsolete_managed_program_files_removed(self):
        self.install()
        (self.target / 'scripts/user.py').write_text('user')
        (self.source / 'scripts/app.py').unlink()
        self.install()
        self.assertFalse((self.target / 'scripts/app.py').exists())
        self.assertEqual((self.target / 'scripts/user.py').read_text(), 'user')

    def test_reject_malicious_previous_manifest(self):
        self.install()
        (self.source / 'scripts/app.py').write_text('new')
        (self.target / installer.MANIFEST).write_text('{"files":{"../../private":"bad"}}')
        with self.assertRaises(ValueError):
            self.install()


if __name__ == '__main__':
    unittest.main()
