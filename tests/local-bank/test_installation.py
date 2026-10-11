from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[2]/'skills/tizhuang-local-bank/scripts'))
import install_local_bank as installer


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root/'package'
        self.vault = self.root/'老师自己的题库'
        self.skill = self.root/'agent/skills/tizhuang-local-bank'
        self.plugin = self.vault/'.obsidian/plugins/tizhuang-question-bank'
        self.make_package('2.4.2', '0.13.1')

    def tearDown(self):
        self.temp.cleanup()

    def make_package(self, sv, pv):
        data = {'schema':'tizhuang.install/v1','version':sv,'components':{},'seed_files':{}}
        for kind, rel, names, ver in [('skill','skills/tizhuang-local-bank',installer.SKILL_FILES,sv),
                ('plugin','题庄本地题库/.obsidian/plugins/tizhuang-question-bank',installer.PLUGIN_FILES,pv)]:
            hashes = {}
            for name in names:
                content = f'program {kind}/{name}'.encode()
                if name == 'SKILL.md':
                    content = b'---\nname: tizhuang-local-bank\ndescription: Test\n---\n'
                if name == 'version.json':
                    content = installer.json_bytes({'name':installer.SKILL,'version':ver})
                if name == 'manifest.json':
                    content = installer.json_bytes({'id':installer.PLUGIN,'version':ver})
                path = self.package/rel/name
                installer.atomic(path,content)
                hashes[name] = installer.digest(content)
            data['components'][kind]={'source':rel,'version':ver,'files':hashes}
        for name in installer.SEED_FILES:
            content = installer.json_bytes({'schema':'tizhuang.bank/v1','ui_layout':'teacher/v2'}) if name.endswith('.json') else '空白首页'.encode()
            installer.atomic(self.package/'题庄本地题库'/name,content)
            data['seed_files'][name]=installer.digest(content)
        installer.atomic(self.package/'installation.json',installer.json_bytes(data))

    def plan(self, **kw):
        return installer.plan(self.package,self.vault,self.skill,**kw)

    def install(self, **kw):
        return installer.apply(self.plan(**kw),skip_runtime=True)

    def snapshot(self, path):
        return {p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file() and '.install-backups' not in p.parts}

    def test_new_install_and_second_run_is_zero_write(self):
        before = self.plan()
        self.assertFalse(self.vault.exists())
        self.assertEqual([c['action'] for c in before['components']],['install','install'])
        result = installer.apply(before,skip_runtime=True)
        self.assertTrue(result['ready'])
        self.assertTrue((self.plugin/'main.js').exists())
        self.assertTrue((self.skill/'SKILL.md').exists())
        self.assertFalse(list((self.vault/'题目库').iterdir()))
        snapshot = self.snapshot(self.root)
        times = {p:p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()}
        result = self.install()
        self.assertEqual(result['written_files'],0)
        self.assertEqual([c['action'] for c in result['components']],['skip_current','skip_current'])
        self.assertEqual(snapshot,self.snapshot(self.root))
        self.assertEqual(times,{p:p.stat().st_mtime_ns for p in times})

    def test_upgrade_keeps_teacher_data_config_old_skill_and_environment(self):
        self.make_package('2.4.1','0.12.0')
        self.install()
        private = {self.vault/'题目库/教师题.md':b'teacher question',self.vault/'资料/附件/figure.png':b'image',
            self.vault/'试卷/老师已编辑.docx':b'edited paper',self.vault/'题库首页.md':'我的首页'.encode(),
            self.vault/'.bank/config.json':installer.json_bytes({'schema':'tizhuang.bank/v1','custom':'keep'}),
            self.vault/'.obsidian/community-plugins.json':b'["other-plugin"]',
            self.plugin/'data.json':b'{"pythonPath":"existing-python","subjectId":2,"keyRef":"private-reference"}',
            self.skill/'.venv/custom':b'private environment', self.skill/'custom.md':b'user note',
            self.skill.parent/'question-bank/SKILL.md':b'old skill must not change'}
        for p, data in private.items(): installer.atomic(p,data)
        self.make_package('2.4.2','0.13.1')
        with patch.object(installer,'probe_python',return_value=True), patch.object(installer.subprocess,'run') as proc:
            result = installer.apply(self.plan())
        proc.assert_not_called()
        self.assertEqual(result['runtime']['status'],'reused')
        self.assertTrue(result['backup_files'])
        for p,data in private.items():self.assertEqual(p.read_bytes(),data,str(p))
        self.assertEqual(result['seed_files'],[])

    def test_current_modified_kept_newer_never_downgraded(self):
        self.install()
        installer.atomic(self.plugin/'main.js',b'my customized program')
        self.assertEqual(self.plan()['components'][0]['action'],'preserve_modified')
        result=self.install()
        self.assertFalse(result['ready'])
        self.assertEqual((self.plugin/'main.js').read_bytes(),b'my customized program')
        installer.atomic(self.skill/'version.json',installer.json_bytes({'name':installer.SKILL,'version':'9.0.0'}))
        snapshot=self.snapshot(self.skill)
        result=self.install(repair=True)
        self.assertEqual(result['components'][1]['action'],'skip_newer')
        self.assertEqual(snapshot,self.snapshot(self.skill))

    def test_missing_program_repaired_without_touching_config(self):
        self.install()
        (self.plugin/'helper/docx_export.py').unlink()
        installer.atomic(self.plugin/'data.json',b'{"preference":"keep"}')
        result=self.install()
        self.assertEqual(result['components'][0]['action'],'repair')
        self.assertEqual((self.plugin/'data.json').read_bytes(),b'{"preference":"keep"}')
        self.assertTrue((self.plugin/'helper/docx_export.py').exists())

    def test_legacy_skill_recognized_and_only_new_skill_installed(self):
        installer.atomic(self.skill/'SKILL.md',b'---\nname: tizhuang-local-bank\n---\nlegacy')
        result=self.install(skip_plugin=True)
        self.assertEqual(result['components'][0]['action'],'update')
        self.assertFalse(self.vault.exists())
        self.assertEqual(installer.read_json(self.skill/'version.json')['version'],'2.4.2')

    def test_unknown_folder_old_skill_and_package_as_vault_rejected(self):
        with self.assertRaises(ValueError):installer.plan(self.package,self.vault,self.skill.parent/'question-bank')
        with self.assertRaises(ValueError):installer.plan(self.package,self.package/'题庄本地题库',self.skill)
        with self.assertRaises(ValueError):installer.plan(self.package,self.vault,self.package/'skills/tizhuang-local-bank')
        installer.atomic(self.skill/'mine.txt',b'other content')
        with self.assertRaises(ValueError):self.plan()
        self.assertEqual((self.skill/'mine.txt').read_bytes(),b'other content')

    def test_tampered_source_and_manifest_rejected_before_any_write(self):
        source=self.package/'skills/tizhuang-local-bank/scripts/local_bank.py'
        installer.atomic(source,b'tampered')
        with self.assertRaisesRegex(ValueError,'校验'):self.install()
        self.assertFalse(self.vault.exists())
        self.make_package('2.4.2','0.13.1')
        data=installer.read_json(self.package/'installation.json')
        data['components']['skill']['files']['../../question-bank/SKILL.md']='0'*64
        installer.atomic(self.package/'installation.json',installer.json_bytes(data))
        with self.assertRaises(ValueError):self.install()

    def test_update_error_restores_program_and_config(self):
        self.make_package('2.4.1','0.12.0');self.install()
        before=self.snapshot(self.vault),self.snapshot(self.skill)
        self.make_package('2.4.2','0.13.1')
        write=installer.atomic
        failed=False
        def fail_once(path,content):
            nonlocal failed
            if Path(path)==self.skill/'version.json' and not failed:
                failed=True
                raise OSError('simulated update failure')
            return write(path,content)
        with patch.object(installer,'atomic',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'simulated'):self.install()
        self.assertEqual(before,(self.snapshot(self.vault),self.snapshot(self.skill)))
        self.assertTrue(self.install()['ready'])

    def test_stale_plan_does_not_overwrite_new_install(self):
        self.install();self.make_package('2.4.3','0.13.2')
        plan=self.plan()
        installer.atomic(self.plugin/'manifest.json',installer.json_bytes({'id':installer.PLUGIN,'version':'9.0.0'}))
        with self.assertRaisesRegex(ValueError,'状态已变化'):installer.apply(plan,skip_runtime=True)
        self.assertEqual(installer.read_json(self.plugin/'manifest.json')['version'],'9.0.0')

    def test_invalid_existing_python_preserved_and_attention_reported(self):
        self.install()
        original=b'{"pythonPath":"missing-python","keyRef":"private-reference"}'
        installer.atomic(self.plugin/'data.json',original)
        with patch.object(installer,'probe_python',return_value=False),patch.object(installer.subprocess,'run') as proc:
            result=installer.apply(self.plan())
        self.assertFalse(result['ready']);self.assertEqual(result['runtime']['status'],'needs_attention')
        self.assertEqual((self.plugin/'data.json').read_bytes(),original)
        proc.assert_not_called()

    def test_missing_python_setting_adds_only_that_field(self):
        self.install()
        prefs={'subjectId':2,'phaseId':2,'keyRef':'private-reference','nested':{'keep':[1,2]}}
        installer.atomic(self.plugin/'data.json',installer.json_bytes(prefs))
        with patch.object(installer,'probe_python',return_value=True):result=installer.apply(self.plan())
        after=installer.read_json(self.plugin/'data.json')
        self.assertTrue(after.pop('pythonPath'))
        self.assertEqual(after,prefs)
        self.assertTrue(result['backup_files'])

    def test_dependency_failure_keeps_old_program_and_settings(self):
        self.install();self.make_package('2.4.3','0.13.2')
        before=self.snapshot(self.plugin),self.snapshot(self.skill)
        with patch.object(installer,'probe_python',return_value=False),patch.object(installer.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'error')):
            with self.assertRaisesRegex(RuntimeError,'尚未更新'):installer.apply(self.plan())
        self.assertEqual(before,(self.snapshot(self.plugin),self.snapshot(self.skill)))

    def test_registered_vault_discovery_reads_no_credentials(self):
        self.install()
        registry=self.root/'obsidian.json'
        installer.atomic(registry,installer.json_bytes({'vaults':{'a':{'path':str(self.vault)},'b':{'path':str(self.vault)}}}))
        result=installer.discover(self.root/'agent',registry)
        self.assertEqual(result['vaults'],[{'path':str(self.vault),'teacher_bank':True}])
        self.assertEqual(result['skills'],[])

    def test_symlink_cannot_redirect_settings_or_programs(self):
        self.vault.mkdir()
        outside=self.root/'outside';outside.mkdir()
        victim=outside/'preserved.txt';victim.write_text('outside data')
        link=self.vault/'.obsidian'
        if os.name=='nt':
            subprocess.run(['cmd','/c','mklink','/J',str(link),str(outside)],capture_output=True,check=True)
        else:
            link.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):installer.apply(self.plan())
        self.assertEqual(victim.read_text(),'outside data')


if __name__=='__main__':unittest.main()
