"""Repair only known generated paper links and empty accidental HTML-name notes."""
import datetime as dt
import re
import uuid
import zipfile


def repair(bank):
    import local_bank as lb
    root = bank.root.resolve()
    changes, empty, papers = [], [], []
    for note in (root / '试卷').glob('*/试卷.md'):
        if not (note.parent / 'manifest.json').is_file():
            continue
        old = note.read_bytes()
        text = old.decode('utf-8-sig')
        if (note.parent / '打印稿/试卷.html').is_file():
            text = text.replace('](试卷/历史打印稿/试卷.html)', '](打印稿/试卷.html)')
        if '```tizhuang-paper' not in text:
            text += '\n```tizhuang-paper\n```\n'
        if text.encode('utf-8') != old:
            changes.append((note, old, text.encode('utf-8')))
        manifest = lb.read_json(note.parent / 'manifest.json')
        papers.append((note, str(manifest.get('title') or note.parent.name).replace('|', '｜')))
    history = root / '试卷/历史打印稿'
    if history.exists():
        for note in history.iterdir():
            if note.is_file() and re.fullmatch(r'试卷\.html(?: \d+)?\.md', note.name) and note.stat().st_size == 0:
                empty.append(note)
    if not changes and not empty:
        return {'repaired': 0, 'archived_empty': 0}
    folder = root / '.bank/paper-repair' / (dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    folder.mkdir(parents=True)
    with zipfile.ZipFile(folder / 'backup.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for path, old, _ in changes:
            z.writestr(path.relative_to(root).as_posix(), old)
        for path in empty:
            z.writestr(path.relative_to(root).as_posix(), b'')
    written, removed = [], []
    try:
        for path, old, new in changes:
            if path.read_bytes() != old:
                raise ValueError('试卷记录正在编辑，停止修复')
            lb.atomic(path, new)
            written.append((path, old, new))
        for path in empty:
            # Every path is resolved and verified inside the known history directory.
            if path.resolve().parent != history.resolve() or path.read_bytes() != b'':
                raise ValueError('历史笔记已改变，停止收起')
            path.unlink()
            removed.append(path)
    except Exception:
        for path in removed:
            if not path.exists():
                lb.atomic(path, b'')
        for path, old, new in reversed(written):
            if path.read_bytes() == new:
                lb.atomic(path, old)
        raise
    return {'repaired': len(changes), 'archived_empty': len(empty), 'backup': str(folder / 'backup.zip')}
