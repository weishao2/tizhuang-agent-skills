"""Package only this skill's program and labelled demo assets, never a workspace."""
import argparse,hashlib,re,zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    files=[root/'SKILL.md',root/'README.md',root/'CHANGELOG.md',root/'.gitignore']
    for name in ['scripts','references','assets','tests']:
        files.extend(f for f in (root/name).rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc')
    for file in files:
        if re.search(rb'\bqsk_[A-Za-z0-9_-]{16,}',file.read_bytes()): raise SystemExit('发现疑似 Key，停止打包。')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(files): z.write(file,'tizhuang-studio/'+file.relative_to(root).as_posix())
    print(f'{len(files)} files; SHA256 {hashlib.sha256(args.output.read_bytes()).hexdigest()}')

if __name__=='__main__':main()
