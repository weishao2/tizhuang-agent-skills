"""Stdlib-only, version-aware installation of the independent teacher tools."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import uuid

SKILL = 'tizhuang-local-bank'
PLUGIN = 'tizhuang-question-bank'
SKILL_FILES = ('SKILL.md', 'version.json', 'agents/openai.yaml',
    'scripts/install_local_bank.py', 'scripts/auto_classify.py', 'scripts/paper_links.py',
    'scripts/local_bank.py', 'scripts/ui_layout.py', 'scripts/teacher_library.py',
    'scripts/pdf_import.py', 'scripts/paper_builder.py', 'scripts/docx_export.py',
    'scripts/paper-print.css', 'scripts/requirements.txt', 'references/install.md',
    'references/family.md', 'references/question-contract.md', 'references/pdf-import.md',
    'references/teacher-workspace.md', 'references/paper-basket.md')
PLUGIN_FILES = ('main.js', 'manifest.json', 'styles.css', 'README.md',
    'third-party-licenses/dompurify.txt', 'third-party-licenses/turndown.txt',
    'third-party-licenses/yaml.txt') + tuple('helper/' + name for name in (
    'auto_classify.py', 'paper_links.py', 'local_bank.py', 'ui_layout.py',
    'teacher_library.py', 'pdf_import.py', 'paper_builder.py', 'docx_export.py',
    'paper-print.css', 'requirements.txt'))
SEED_FILES = ('.bank/config.json', '题库首页.md')
FOLDERS = ('题目库', '试卷', '待整理', '教学笔记', '资料/附件', '资料/原件',
    '资料/知识目录', '资料/教材目录', '.bank/records', '.bank/taxonomy', '.bank/textbooks')
RECEIPT = '.tizhuang-install.json'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def child(root, relative):
    root = Path(root).resolve()
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or '\\' in relative or ':' in relative:
        raise ValueError('安装清单包含非法路径')
    path = root.joinpath(*rel.parts)
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError('安装路径通过链接指向了其他位置：' + relative)
    return path


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('不能自动比较该版本，请保留现有安装：' + str(value))
    return tuple(map(int, value.split('.')))


def discover(home=None, registry=None):
    home = Path(home) if home else Path.home()
    if registry is None:
        if sys.platform == 'win32':
            registry = Path(os.environ.get('APPDATA', home/'AppData/Roaming'))/'obsidian/obsidian.json'
        elif sys.platform == 'darwin':
            registry = home/'Library/Application Support/obsidian/obsidian.json'
        else:
            registry = Path(os.environ.get('XDG_CONFIG_HOME', home/'.config'))/'obsidian/obsidian.json'
    vaults, warnings = [], []
    if Path(registry).is_file():
        try:
            for item in read_json(registry).get('vaults', {}).values():
                path = Path(item['path']).expanduser().resolve()
                if not path.is_dir() or any(row['path'] == str(path) for row in vaults):
                    continue
                teacher = (path/'.bank/config.json').is_file() or (path/f'.obsidian/plugins/{PLUGIN}/manifest.json').is_file()
                vaults.append({'path': str(path), 'teacher_bank': teacher})
        except (ValueError, KeyError, TypeError, OSError):
            warnings.append('Obsidian 的仓库登记无法读取，请由用户指定题库位置。')
    roots = [home/'.codex/skills', home/'.agents/skills', home/'.claude/skills']
    return {'vaults': vaults, 'skills': [str(p/SKILL) for p in roots if (p/SKILL).is_dir()],
            'warnings': warnings}


def load_package(root):
    root = Path(root).resolve()
    data = read_json(root/'installation.json')
    if data.get('schema') != 'tizhuang.install/v1' or set(data.get('components', {})) != {'skill', 'plugin'}:
        raise ValueError('这不是支持自动安装的题庄初始包')
    version(data['version'])
    for kind, allowed, source in (
            ('skill', SKILL_FILES, 'skills/'+SKILL),
            ('plugin', PLUGIN_FILES, '题庄本地题库/.obsidian/plugins/'+PLUGIN)):
        part = data['components'][kind]
        version(part['version'])
        if part.get('source') != source or set(part.get('files', {})) != set(allowed):
            raise ValueError('安装清单与独立组件文件列表不一致')
        for name, sha in part['files'].items():
            if digest(child(root, source+'/'+name).read_bytes()) != sha:
                raise ValueError('安装包文件校验失败：' + name)
    if set(data.get('seed_files', {})) != set(SEED_FILES):
        raise ValueError('空白题库模板清单不正确')
    for name, sha in data['seed_files'].items():
        if digest(child(root, '题庄本地题库/'+name).read_bytes()) != sha:
            raise ValueError('空白题库模板校验失败：' + name)
    sv = read_json(root/'skills'/SKILL/'version.json')
    pv = read_json(root/'题庄本地题库/.obsidian/plugins'/PLUGIN/'manifest.json')
    if sv != {'name': SKILL, 'version': data['components']['skill']['version']} or pv.get('id') != PLUGIN or pv.get('version') != data['components']['plugin']['version']:
        raise ValueError('组件标识或版本与安装清单不一致')
    return data


def protect_target(path):
    path = Path(path).expanduser().absolute()
    resolved = path.resolve()
    if 'question-bank' in {p.casefold() for p in path.parts + resolved.parts}:
        raise ValueError('安装目标不能位于旧 question-bank skill 内')
    if path.is_symlink() or path != resolved:
        raise ValueError('安装目标不能是符号链接或目录联接，请使用实际路径')
    return resolved


def inspect_component(kind, target, part, repair=False):
    target = protect_target(target)
    if kind == 'skill' and target.name != SKILL:
        raise ValueError('新 skill 的目录名称必须为 tizhuang-local-bank')
    marker = child(target, 'version.json' if kind == 'skill' else 'manifest.json')
    installed = None
    if marker.exists():
        info = read_json(marker)
        if info.get('name' if kind == 'skill' else 'id') != (SKILL if kind == 'skill' else PLUGIN):
            raise ValueError('目标目录属于其他工具，保留现有文件')
        installed = info['version']
    elif kind == 'skill' and (target/'SKILL.md').exists():
        text = (target/'SKILL.md').read_text(encoding='utf-8-sig')
        if not re.search(r'(?m)^name:\s*tizhuang-local-bank\s*$', text):
            raise ValueError('目标 skill 不是 tizhuang-local-bank')
    elif target.exists() and any(target.iterdir()):
        raise ValueError('目标程序目录没有可识别的组件标识，请由 Agent 核对')
    changed, missing = [], []
    for name, sha in part['files'].items():
        file = child(target, name)
        if not file.exists():
            missing.append(name)
        elif not file.is_file():
            raise ValueError('程序文件位置被目录占用：'+name)
        elif digest(file.read_bytes()) != sha:
            changed.append(name)
    if installed and version(installed) > version(part['version']):
        action, writes = 'skip_newer', []
    elif installed == part['version']:
        if changed and not repair:
            action, writes = 'preserve_modified', []
        else:
            writes = missing + changed
            action = 'repair' if writes else 'skip_current'
    else:
        action = 'update' if installed or (target/'SKILL.md').exists() else 'install'
        writes = missing + changed
    return {'component': kind, 'target': str(target), 'installed_version': installed,
            'available_version': part['version'], 'action': action, 'files': writes}


def plan(package, vault=None, skill_dir=None, skip_plugin=False, skip_skill=False, repair=False):
    package = Path(package).resolve()
    data = load_package(package)
    if skip_plugin and skip_skill:
        raise ValueError('请至少选择一个组件')
    result = {'package': str(package), 'version': data['version'], 'components': [], 'vault': None, 'seed_files': []}
    if not skip_plugin:
        if vault is None:
            found = discover()
            candidates = [v['path'] for v in found['vaults'] if v['teacher_bank']]
            if len(candidates) != 1:
                raise ValueError('需要指定题库位置；使用 --discover 查看已登记的题库，再传 --vault。')
            vault = candidates[0]
        vault = protect_target(vault)
        if vault == package or vault.is_relative_to(package):
            raise ValueError('请选择安装包以外的持久题库位置，避免更新包时丢失题库')
        result['vault'] = str(vault)
        config = child(vault, '.bank/config.json')
        if config.exists():
            if read_json(config).get('schema') != 'tizhuang.bank/v1':
                raise ValueError('题库格式不同，保留原题库并停止自动安装')
        else:
            result['seed_files'] = [n for n in SEED_FILES if not child(vault, n).exists()]
        result['components'].append(inspect_component('plugin', vault/'.obsidian/plugins'/PLUGIN, data['components']['plugin'], repair))
    if not skip_skill:
        if skill_dir is None:
            raise ValueError('需要指定当前 Agent 的新 skill 目录，或用 --agent codex；不要猜其他 Agent 的安装位置')
        if Path(skill_dir).resolve().is_relative_to(package):
            raise ValueError('新 skill 应安装到 Agent 的持久目录，不能安装到解压包自身')
        result['components'].append(inspect_component('skill', skill_dir, data['components']['skill'], repair))
    roots = [Path(p['target']) for p in result['components']]
    if any(a == b or a.is_relative_to(b) or b.is_relative_to(a) for i, a in enumerate(roots) for b in roots[i+1:]):
        raise ValueError('插件与 skill 安装目录不能重叠')
    return result


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.install-' + uuid.uuid4().hex)
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf-8')


def probe_python(executable, requirements):
    # No shell and no package installation in an existing user's environment.
    check = '''import importlib, importlib.metadata as m, json, re, sys
assert sys.version_info >= (3,10)
for name in ['yaml','markdown','latex2mathml.converter','pdfplumber','pypdfium2','PIL','docx','mathml2omml']:
    importlib.import_module(name)
def ver(v):
    match=re.match(r'^(\\d+)\\.(\\d+)(?:\\.(\\d+))?',v)
    return tuple(int(n or 0) for n in match.groups())
for line in json.loads(sys.argv[1]).splitlines():
    line=line.strip()
    if not line or line.startswith('#'): continue
    pkg=re.match(r'[A-Za-z0-9_.-]+',line).group()
    actual=ver(m.version(pkg))
    for op,want in re.findall(r'(>=|<|==)([0-9.]+)',line[len(pkg):]):
        target=tuple(int(n) for n in want.split('.')); target=target+(0,)*(3-len(target))
        assert {'>=':actual>=target,'<':actual<target,'==':actual==target}[op],pkg
'''
    try:
        proc = subprocess.run([str(executable), '-c', check, json.dumps(requirements)], capture_output=True, timeout=25)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def prepare_runtime(result, requirements_file):
    parts = {p['component']: p for p in result['components']}
    if any(p['action'] in ('preserve_modified', 'skip_newer') for p in parts.values()):
        return {'status': 'skipped', 'reason': '保留修改版或较新组件，不调整其运行环境'}, None
    settings_path = None
    settings = {}
    if result['vault']:
        settings_path = child(Path(parts['plugin']['target']), 'data.json')
        if settings_path.exists():
            settings = read_json(settings_path)
            if not isinstance(settings, dict):
                raise ValueError('插件设置格式无效，保留原文件')
    requirements = requirements_file.read_text(encoding='utf-8-sig')
    configured = settings.get('pythonPath')
    if configured:
        if probe_python(configured, requirements):
            return {'status': 'reused', 'python': configured}, None
        return {'status': 'needs_attention', 'reason': '原 pythonPath 不可用或缺少依赖，已保留原配置；请由 Agent 修复该路径或征求同意后切换独立环境'}, None
    name = 'tizhuang-local-bank-'+digest(requirements.encode())[:12]
    runtime = child(Path(result['vault']), '.bank/runtimes/'+name) if result['vault'] else child(
        Path(parts['skill']['target']).parent, '.tizhuang-local-bank-runtimes/'+name)
    runtime = protect_target(runtime)
    python = runtime/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not probe_python(python, requirements):
        if runtime.exists() and not (runtime/'.tizhuang-runtime.json').exists():
            raise ValueError('运行环境目录已有未知文件，保留并停止；请由 Agent 核对')
        runtime.mkdir(parents=True, exist_ok=True)
        atomic(runtime/'.tizhuang-runtime.json', json_bytes({'owner': SKILL}))
        for command in ([sys.executable, '-m', 'venv', str(runtime)],
                        [str(python), '-m', 'pip', 'install', '-r', str(requirements_file)]):
            proc = subprocess.run(command, capture_output=True, timeout=300)
            if proc.returncode:
                (runtime/'installation.log').write_bytes(proc.stdout+proc.stderr)
                raise RuntimeError('独立运行环境准备失败；程序和用户配置尚未更新，日志：'+str(runtime/'installation.log'))
        if not probe_python(python, requirements):
            raise RuntimeError('独立运行环境校验未通过')
    settings_write = None
    if settings_path:
        settings['pythonPath'] = str(python)
        settings_write = (settings_path, json_bytes(settings))
    return {'status': 'ready', 'python': str(python)}, settings_write


def apply(result, skip_runtime=False):
    # Recompute immediately before mutation; a saved plan is never authority to overwrite newer files.
    args = {p['component']: p for p in result['components']}
    current = plan(result['package'], result['vault'], args.get('skill', {}).get('target'),
                   skip_plugin='plugin' not in args, skip_skill='skill' not in args,
                   repair=any(p['action']=='repair' for p in args.values()))
    if current != result:
        raise ValueError('安装状态已变化，请重新检查后安装')
    package = Path(result['package'])
    data = load_package(package)
    runtime, settings_write = ({'status': 'skipped'}, None) if skip_runtime else prepare_runtime(result, package/'skills'/SKILL/'scripts/requirements.txt')
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    writes = []
    for part in result['components']:
        target = Path(part['target'])
        source = data['components'][part['component']]['source']
        for name in part['files']:
            writes.append((child(target, name), child(package, source+'/'+name).read_bytes(), target/'.install-backups'/run_id/name))
        if part['action'] in ('install', 'update', 'repair', 'skip_current'):
            previous = read_json(child(target, RECEIPT)) if child(target, RECEIPT).exists() else {}
            receipt = {'schema': 'tizhuang.installed/v1', 'version': part['available_version'], 'component': part['component'],
                       'files': data['components'][part['component']]['files'],
                       'runtime': {'python': runtime['python']} if runtime.get('python') else previous.get('runtime', {})}
            if receipt != previous:
                writes.append((child(target, RECEIPT), json_bytes(receipt), target/'.install-backups'/run_id/RECEIPT))
    if result['vault']:
        vault = Path(result['vault'])
        for name in result['seed_files']:
            writes.append((child(vault, name), child(package, '题庄本地题库/'+name).read_bytes(), vault/'.bank/install-backups'/run_id/name))
        if settings_write:
            path, content = settings_write
            writes.append((path, content, Path(args['plugin']['target'])/'.install-backups'/run_id/'data.json'))
    before, backups = {}, []
    for path, content, backup in writes:
        protect_target(path)
        protect_target(backup)
        before[path] = path.read_bytes() if path.exists() else None
        if before[path] is not None:
            atomic(backup, before[path])
            backups.append(str(backup))
    touched = []
    try:
        for path, content, _ in writes:
            if (path.read_bytes() if path.exists() else None) != before[path]:
                raise ValueError('安装期间文件发生变化，已停止并回退')
            touched.append(path)
            atomic(path, content)
        if result['seed_files']:
            for name in FOLDERS:
                child(Path(result['vault']), name).mkdir(parents=True, exist_ok=True)
    except Exception:
        for path in reversed(touched):
            if before[path] is None:
                if path.exists():
                    path.unlink()
            else:
                atomic(path, before[path])
        roots = [Path(p['target']) for p in result['components']]
        for path in reversed(touched):
            parent = path.parent
            while any(parent == root or parent.is_relative_to(root) for root in roots):
                try:
                    parent.rmdir()  # Only empty directories created during this attempt.
                except OSError:
                    break
                parent = parent.parent
        raise
    return {**result, 'runtime': runtime, 'written_files': len(writes), 'backup_files': backups,
            'ready': runtime['status'] != 'needs_attention' and all(p['action']!='preserve_modified' for p in result['components']),
            'next': '首次使用需在 Obsidian 启用插件；更新后重载插件。新 skill 安装后重新开启 Agent 会话。'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='题庄本地题库：检查版本，安装、更新或跳过，保留原题与配置')
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--skill-dir', type=Path)
    parser.add_argument('--agent', choices=['codex'])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--discover', action='store_true')
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--skip-plugin', action='store_true')
    parser.add_argument('--skip-skill', action='store_true')
    parser.add_argument('--skip-runtime', action='store_true', help='仅安装程序，不配置 PDF/Word 的独立环境')
    parser.add_argument('--repair', action='store_true', help='用户明确要求修复时，备份并替换同版本修改过的程序')
    args = parser.parse_args(argv)
    try:
        if args.discover:
            value = discover()
        else:
            target = args.skill_dir
            if target is None and args.agent == 'codex':
                target = Path(os.environ.get('CODEX_HOME', Path.home()/'.codex'))/'skills'/SKILL
            value = plan(args.package, args.vault, target, args.skip_plugin, args.skip_skill, args.repair)
            if args.apply:
                value = apply(value, args.skip_runtime)
        print(json.dumps({'ok': True, 'result': value}, ensure_ascii=False, indent=2))
        return 2 if value.get('ready') is False else 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
