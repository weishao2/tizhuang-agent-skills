import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace
script = Path(__file__).resolve().parents[3] / 'skills/tizhuang-local-bank/scripts/local_bank.py'
sys.path.insert(0, str(script.parent))
spec = importlib.util.spec_from_file_location('local_bank', script)
lb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lb)
bank = lb.Bank(sys.argv[1])
questions = bank.questions()
assert len(questions) == 1
q = questions[0]
is_knowledge = bool(q['knowledge_tree_ids'])
assert q['status'] == 'draft'
assert (q['edition_id'] is None and q['chapter_ids'] == [] and q['knowledge_tree_ids'] == ['11']) if is_knowledge else (q['edition_id'] == 59 and q['chapter_ids'] == ['10'])
args = SimpleNamespace(subject=2, phase=2, grade=None, edition=None if is_knowledge else 59, chapter=None if is_knowledge else '10', knowledge='10' if is_knowledge else None, type=None, tag=None, query='一次函数', status=None, unused=False, ids=None, count=1, title='插件互通测试卷', plan=False)
assert len(bank.select(args)) == 1
args.edition = 142
args.chapter = None
assert bank.select(args) == []
args.edition = None if is_knowledge else 59
args.chapter = None if is_knowledge else '10'
# A teacher must explicitly review before the independent skill assembles a paper.
try:
    lb.paper(bank, args)
    raise AssertionError('draft should not assemble')
except ValueError as exc:
    assert 'reviewed' in str(exc)
path = bank.note_paths[q['id']]
path.write_text(path.read_text(encoding='utf-8').replace('审核状态: 待核对', '审核状态: 已核对'), encoding='utf-8')
paper = lb.paper(bank, args)
assert Path(paper['student']).is_file() and Path(paper['teacher']).is_file()
assert '子答案' not in Path(paper['student']).read_text(encoding='utf-8')
assert '子答案' in Path(paper['teacher']).read_text(encoding='utf-8')
print('cross-skill-ok')
