"""Publish only allowlisted teacher tools and a freshly created empty vault."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.4.1'
SKILL_FILES = ['SKILL.md', 'agents/openai.yaml', 'scripts/auto_classify.py',
    'scripts/paper_links.py', 'scripts/local_bank.py', 'scripts/ui_layout.py',
    'scripts/teacher_library.py', 'scripts/pdf_import.py', 'scripts/paper_builder.py',
    'scripts/docx_export.py', 'scripts/paper-print.css', 'scripts/requirements.txt',
    'references/family.md', 'references/question-contract.md', 'references/pdf-import.md',
    'references/teacher-workspace.md', 'references/paper-basket.md']
PLUGIN_FILES = ['main.js', 'manifest.json', 'styles.css', 'README.md'] + [
    'helper/'+name for name in ['auto_classify.py', 'paper_links.py', 'local_bank.py',
    'ui_layout.py', 'teacher_library.py', 'pdf_import.py', 'paper_builder.py',
    'docx_export.py', 'paper-print.css', 'requirements.txt']]

def build(output):
    skill=ROOT/'skills/tizhuang-local-bank'
    plugin=ROOT/'plugins/obsidian/dist/tizhuang-question-bank'
    manifest=json.loads((plugin/'manifest.json').read_text(encoding='utf-8-sig'))
    assert manifest['version']=='0.13.1' and manifest['id']=='tizhuang-question-bank'
    output.mkdir(parents=True,exist_ok=True)
    archive=output/f'tizhuang-local-bank-starter-v{VERSION}.zip'
    files={}
    for rel in SKILL_FILES:
        files['skills/tizhuang-local-bank/'+rel]=(skill/rel).read_bytes()
    prefix='题庄本地题库/.obsidian/plugins/tizhuang-question-bank/'
    for rel in PLUGIN_FILES:
        files[prefix+rel]=(plugin/rel).read_bytes()
        if rel.startswith('helper/'):
            assert files[prefix+rel]==(skill/'scripts'/Path(rel).name).read_bytes()
    for name in ['dompurify.txt','turndown.txt','yaml.txt']:
        files[prefix+'third-party-licenses/'+name]=(ROOT/'plugins/obsidian/third-party-licenses'/name).read_bytes()
    for name in ['README.md','安装本地环境.ps1']:
        files[name]=(ROOT/'templates/local-bank-starter'/name).read_bytes()
    files['LICENSE']=(ROOT/'LICENSE').read_bytes()
    files['题庄本地题库/.bank/config.json']=json.dumps({'schema':'tizhuang.bank/v1','ui_layout':'teacher/v2'},ensure_ascii=False,indent=2).encode('utf-8')
    files['题庄本地题库/题库首页.md']=('''# 题库首页

共 **0** 题 · 试卷 **0** 份

```tizhuang-dashboard
```

启用“题庄本地题库”插件后，可打开题库工作台。

- 网站取题：配置自己的凭证，再选章节或知识点取题。
- 导入 PDF：准备原页后复制 Agent 指令，识别、分类并核对。
- 我的题目：按知识点和标签浏览，核对后加入组卷篮。
- 组卷篮：调题序、分值，生成无答案与教师答案 Word。

这是空白起步题库。你自己的备课笔记放在“教学笔记”；图片、原件和知识目录由工具写入“资料”。
''').encode('utf-8')
    folders=['题目库','试卷','待整理','教学笔记','资料/附件','资料/原件','资料/知识目录','资料/教材目录','.bank/records','.bank/taxonomy','.bank/textbooks']
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for folder in folders:
            z.writestr('题庄本地题库/'+folder+'/',b'')
        for name,data in sorted(files.items()):
            assert not any(part in {'__pycache__','.venv','.git','node_modules'} for part in Path(name).parts)
            assert not name.endswith(('data.json','.sqlite3','.pdf','.pyc'))
            z.writestr(name,data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert {n for n in z.namelist() if not n.endswith('/')}==set(files)
    sha=hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/'SHA256SUMS.txt').write_text(f'{sha}  {archive.name}\n',encoding='utf-8')
    report={'skill_version':VERSION,'plugin_version':manifest['version'],'archive':archive.name,'sha256':sha,
        'files':len(files),'initial_questions':0,'initial_papers':0,'contains_account_settings':False,
        'source_hashes':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}}
    (output/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'downloads/local-bank'/f'v{VERSION}')
    build(parser.parse_args().output)
