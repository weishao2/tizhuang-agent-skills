"""Publish only allowlisted teacher tools and a freshly created empty vault."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/tizhuang-local-bank/scripts'))
from install_local_bank import SKILL_FILES, PLUGIN_FILES, FOLDERS, SEED_FILES
VERSION = json.loads((ROOT/'skills/tizhuang-local-bank/version.json').read_text())['version']

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
        source = ROOT/'plugins/obsidian'/rel if rel.startswith('third-party-licenses/') else plugin/rel
        files[prefix+rel]=source.read_bytes()
        if rel.startswith('helper/'):
            assert files[prefix+rel]==(skill/'scripts'/Path(rel).name).read_bytes()
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
    install = {'schema':'tizhuang.install/v1', 'version':VERSION, 'components':{},
        'seed_files': {name:hashlib.sha256(files['题庄本地题库/'+name]).hexdigest() for name in SEED_FILES}}
    for kind, source, rels, ver in [('skill','skills/tizhuang-local-bank',SKILL_FILES,VERSION),
            ('plugin',prefix.rstrip('/'),PLUGIN_FILES,manifest['version'])]:
        install['components'][kind]={'source':source,'version':ver,
            'files':{name:hashlib.sha256(files[source+'/'+name]).hexdigest() for name in rels}}
    files['installation.json']=(json.dumps(install,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for folder in FOLDERS:
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
    if output.resolve() == (ROOT/'downloads/local-bank'/f'v{VERSION}').resolve():
        latest={'version':VERSION,'plugin_version':manifest['version'],'sha256':sha,
            'url':f'https://raw.githubusercontent.com/weishao2/tizhuang-agent-skills/local-bank-v{VERSION}/downloads/local-bank/v{VERSION}/{archive.name}',
            'agent_install':'https://github.com/weishao2/tizhuang-agent-skills/blob/main/docs/local-bank/INSTALL.md'}
        (output.parent/'latest.json').write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'downloads/local-bank'/f'v{VERSION}')
    build(parser.parse_args().output)
