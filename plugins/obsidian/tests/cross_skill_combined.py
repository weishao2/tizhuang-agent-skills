import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'skills/tizhuang-local-bank/scripts'))
import local_bank as lb
bank = lb.Bank(sys.argv[1])
q = bank.questions()[0]
assert q['edition_id'] == 59 and q['chapter_ids'] == ['10'] and q['knowledge_tree_ids'] == ['11']
args = SimpleNamespace(subject=2, phase=2, grade=None, edition=59, chapter='10', knowledge='9', type=None, tag=None, query='一次函数', status=None, unused=False)
assert len(bank.select(args)) == 1
args.edition = 142
args.chapter = None
assert bank.select(args) == []
assert q['status'] == 'draft'
print('combined-skill-ok')
