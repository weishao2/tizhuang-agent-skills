"""Standard-library installer. Program files and the user's workspace stay separate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = '.studio-install.json'


def version(root):
    return re.search(r'^  version:\s*(\S+)', (root / 'SKILL.md').read_text(encoding='utf-8'), re.M)[1]


def files(root):
    result = [root / name for name in ('SKILL.md', 'README.md', '.gitignore')]
    if (root / 'CHANGELOG.md').is_file(): result.append(root / 'CHANGELOG.md')
    for name in ('scripts', 'references', 'assets'):
        result += [p for p in (root / name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    if any(p.is_symlink() for p in result):
        raise ValueError('安装包不能包含符号链接。')
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in result}


def install_program(source, target, workspace):
    source, target, workspace = (Path(p).resolve() for p in (source, target, workspace))
    if target.name != 'tizhuang-studio':
        raise ValueError('安装目录名称必须是 tizhuang-studio，不能覆盖其他 Skill。')
    if workspace == target or workspace in target.parents or target in workspace.parents:
        raise ValueError('题库目录与程序目录必须分开，不能互相包含。')
    if any((target / marker).exists() for marker in ('studio.sqlite3', 'session.json', '.obsidian', '.bank')):
        raise ValueError('目标目录含题库数据，请选择独立的 Skill 安装目录。')
    if target.exists() and any(target.iterdir()) and not (target / 'SKILL.md').exists():
        raise ValueError('目标目录不是可识别的工作台安装，已保留原文件。')
    if (target / 'SKILL.md').exists() and not re.search(r'^name:\s*tizhuang-studio\s*$', (target / 'SKILL.md').read_text(encoding='utf-8'), re.M):
        raise ValueError('目标目录属于其他 Skill，不能覆盖。')
    current = version(target) if (target / 'SKILL.md').exists() else None
    incoming = version(source)
    numeric = lambda v: tuple(map(int, v.split('-')[0].split('.')))
    if current and numeric(current) > numeric(incoming):
        return {'action': 'skip-newer', 'version': current}
    hashes = files(source)
    old = json.loads((target / MANIFEST).read_text(encoding='utf-8')) if (target / MANIFEST).exists() else {}
    # Only old managed files may be removed. Never remove unknown user files or .venv.
    previous = old.get('files', {})
    allowed = lambda name: not Path(name).is_absolute() and '..' not in Path(name).parts and (name in ('SKILL.md', 'README.md', 'CHANGELOG.md', '.gitignore') or name.startswith(('scripts/', 'references/', 'assets/')))
    if any(not allowed(name) for name in previous):
        raise ValueError('旧安装清单路径异常，停止更新。')
    if not (set(previous) - set(hashes)) and all((target / name).is_file() and hashlib.sha256((target / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items()):
        return {'action': 'skip', 'version': incoming}
    target.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='tizhuang-studio-backup-', dir=target.parent)) if current else None
    changed = []
    try:
        for name in sorted(set(hashes) | set(previous)):
            dest = target / name
            if dest.is_symlink() or any(p.is_symlink() for p in dest.parents if p != target.parent):
                raise ValueError('安装路径包含符号链接，停止更新。')
            existed = dest.exists()
            if existed and backup:
                (backup / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup / name)
            changed.append((name, existed))
            if name in hashes:
                dest.parent.mkdir(parents=True, exist_ok=True)
                temp = dest.with_name(dest.name + '.install-tmp')
                shutil.copy2(source / name, temp)
                os.replace(temp, dest)
            elif existed:
                dest.unlink()
        (target / MANIFEST).write_text(json.dumps({'version': incoming, 'files': hashes, 'installed_at': datetime.now().isoformat()}, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        for name, existed in reversed(changed):
            dest = target / name
            if existed and backup and (backup / name).exists():
                shutil.copy2(backup / name, dest)
            elif not existed and dest.exists():
                dest.unlink()
        raise
    return {'action': 'update' if current else 'install', 'version': incoming, 'backup': str(backup) if backup else None}


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        # pip output may contain private package-index credentials. Do not echo it.
        raise RuntimeError('环境配置未完成。请检查网络后使用同一安装命令重试；题库数据未修改。')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description='安装/更新题庄工作台，自动配置独立环境并体检。')
    parser.add_argument('--target', type=Path, required=True, help='Agent 的 skills/tizhuang-studio 路径')
    parser.add_argument('--workspace', type=Path, required=True, help='独立题库数据目录')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        raise ValueError('需要 Python 3.10 或更新版本。')
    target = args.target.resolve()
    result = install_program(ROOT, target, args.workspace)
    env = target / '.venv'
    python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        run([sys.executable, '-m', 'venv', str(env)])
    requirements = target / 'scripts/requirements.txt'
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = env / '.studio-requirements.sha256'
    doctor_cmd = [str(python), '-X', 'utf8', str(target / 'scripts/studio.py'), '--workspace', str(args.workspace.resolve()), 'doctor']
    check = subprocess.run(doctor_cmd, capture_output=True, text=True, encoding='utf-8')
    if check.returncode or not marker.exists() or marker.read_text() != digest:
        run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(requirements)])
        marker.write_text(digest)
    doctor = json.loads(run(doctor_cmd))
    if not doctor.get('ok'):
        raise RuntimeError('环境体检未通过，请让 Agent 检查独立环境。')
    print(json.dumps(result | {'ok': True, 'python': str(python), 'workspace': str(args.workspace.resolve()), 'doctor': doctor, 'next': '运行 scripts/start.ps1 启动；已有工作台会复用。'}, ensure_ascii=False))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        main()
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, (ValueError, RuntimeError)) else '安装未完成，原题库已保留。', 'hint': '检查目标路径与 Python/网络后重试，不要删除题库。'}, ensure_ascii=False))
        sys.exit(1)
