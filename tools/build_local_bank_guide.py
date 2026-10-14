"""Build a self-contained teacher guide; screenshots are embedded, never fetched."""
import base64
from pathlib import Path
import re
import markdown

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / 'docs/local-bank'
SCREENSHOTS = ('01-home.png', '02-website.png', '03-knowledge.png', '04-tags.png',
               '05-classify.png', '06-pdf.png', '07-basket.png', '08-word-output.png')

CSS = '''
:root{color-scheme:light;--ink:#272334;--muted:#6d657b;--accent:#704ac9;--line:#e7e2ef}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:28px}
body{margin:0;background:#f6f4fa;color:var(--ink);font:17px/1.85 "Segoe UI","Microsoft YaHei",sans-serif}
a{color:#6540bd;text-underline-offset:4px;overflow-wrap:anywhere}a:hover{color:#3f237d}
.layout{max-width:1330px;margin:auto;display:grid;grid-template-columns:230px minmax(0,1fr);gap:40px;padding:40px 28px}
aside{position:sticky;top:30px;align-self:start;font-size:14px}aside strong{display:block;font-size:22px;color:var(--ink);margin-bottom:20px}aside a{display:block;color:var(--muted);text-decoration:none;padding:9px 12px;border-radius:8px}aside a:hover{background:#eae4f5;color:var(--accent)}
main{min-width:0;background:white;padding:48px 52px 60px;border:1px solid var(--line);border-radius:20px;box-shadow:0 10px 40px #33225c05}
.eyebrow{font-size:12px;letter-spacing:.2em;color:var(--accent);font-weight:700}h1{font-size:36px;line-height:1.35;margin:14px 0 24px;letter-spacing:-.02em}h2{font-size:27px;line-height:1.5;margin:56px 0 22px;padding-top:24px;border-top:1px solid var(--line)}h3{font-size:20px;margin:30px 0 12px}p{margin:14px 0}li{margin:8px 0}strong{font-weight:650}blockquote{margin:22px 0;padding:4px 20px;border-left:3px solid #9e83d6;background:#f7f4fc;color:var(--muted);font-size:14px}
table{border-collapse:collapse;width:100%;font-size:15px;margin:22px 0;table-layout:fixed}th,td{border-bottom:1px solid var(--line);padding:12px 14px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#f5f2fb}th:first-child,td:first-child{width:30%}
code{font-family:Consolas,"Microsoft YaHei",monospace;font-size:.92em;background:#f4f0fa;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}pre{position:relative;background:#f5f2fa;border:1px solid var(--line);border-radius:12px;padding:52px 20px 20px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;font-size:14px}pre code{padding:0;background:none}
button{font:inherit;cursor:pointer;border:1px solid #d8cfe8;border-radius:8px;padding:8px 13px;background:white;color:var(--accent)}button:hover{background:#f0eaf9}.copy{position:absolute;top:10px;right:12px;font-size:12px;padding:4px 12px}.print{margin-top:24px;width:100%}
img{display:block;max-width:100%;height:auto;margin:28px auto 10px;border:1px solid var(--line);border-radius:10px;cursor:zoom-in}p:has(>img)+p{font-size:13px;color:var(--muted);margin-top:10px}.toplink{font-size:13px;color:var(--muted)}dialog{max-width:96vw;width:1160px;max-height:94vh;overflow:auto;border:1px solid var(--line);border-radius:14px;padding:18px;background:white}dialog::backdrop{background:#191329bb}dialog img{margin:15px auto 0;border:0;cursor:default}dialog button{position:sticky;top:0;float:right}
@media(max-width:900px){.layout{display:block;padding:16px}.layout>aside{position:static;margin:8px 8px 24px}.layout>aside nav{display:flex;flex-wrap:wrap}.layout>aside a{padding:6px 10px}.print{width:auto;margin:8px 0}main{padding:28px 24px}h1{font-size:30px}h2{font-size:24px}}
@media(max-width:480px){body{font-size:16px}.layout{padding:10px}main{padding:24px 16px}h1{font-size:27px}th,td{padding:9px 6px;font-size:13px}pre{padding-left:12px;padding-right:12px}blockquote{padding-left:12px}ul,ol{padding-left:24px}}
@media print{body{background:white}.layout{display:block;padding:0}.layout>aside,.copy,.toplink{display:none}main{border:0;padding:0;box-shadow:none}h2{break-before:page}img,table,pre{break-inside:avoid}a{color:inherit}dialog{display:none}}
'''
SCRIPT = '''
for(const pre of document.querySelectorAll('pre')){
 const b=document.createElement('button');b.className='copy';b.textContent='复制指令';b.type='button';
 b.onclick=async()=>{const text=pre.querySelector('code').textContent;let ok=false;
  try{await navigator.clipboard.writeText(text);ok=true;}catch{const a=document.createElement('textarea');a.value=text;document.body.append(a);a.select();ok=document.execCommand('copy');a.remove();}
  b.textContent=ok?'已复制':'请手动选择并复制';setTimeout(()=>b.textContent='复制指令',2000);};pre.prepend(b);
}
const modal=document.querySelector('dialog'),preview=modal.querySelector('img');
for(const img of document.querySelectorAll('main img')){img.tabIndex=0;img.setAttribute('role','button');img.setAttribute('aria-label','放大截图：'+img.alt);const show=()=>{preview.src=img.src;preview.alt=img.alt;modal.showModal();};img.onclick=show;img.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show();}};}
modal.querySelector('button').onclick=()=>modal.close();document.querySelector('.print').onclick=()=>window.print();
'''


def build():
    text = (GUIDE / 'USER_GUIDE.md').read_text(encoding='utf-8')
    names = re.findall(r'!\[[^\]]*\]\(screenshots/([^\)]+)\)', text)
    assert set(names) == set(SCREENSHOTS) and len(names) == len(SCREENSHOTS)
    body = markdown.markdown(text, extensions=['tables', 'fenced_code'])
    # The standalone page already has navigation; retain the TOC in Markdown only.
    body = re.sub(r'<h2>目录</h2>\s*<ul>[\s\S]*?</ul>', '', body, count=1)
    for name in SCREENSHOTS:
        data = base64.b64encode((GUIDE / 'screenshots' / name).read_bytes()).decode('ascii')
        body = body.replace('src="screenshots/' + name + '"', 'src="data:image/png;base64,' + data + '"')
    assert 'src="screenshots/' not in body
    sections = [('install','01 拿到包，先安装'),('open','02 打开 Obsidian 题库'),
                ('website','03 从网站取题'),('pdf','04 导入 PDF'),('classify','05 分类与找题'),
                ('paper','06 组卷与 Word'),('agent','07 交给 Agent 做'),('help','08 更新与常见问题')]
    nav = ''.join(f'<a href="#{key}">{title}</a>' for key,title in sections)
    html = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>题庄本地题库 · 老师使用说明</title><style>' + CSS + '</style></head>'
            '<body id="top"><div class="layout"><aside><strong>题庄 · 本地题库</strong><nav>' + nav +
            '</nav><button class="print" type="button">打印 / 保存为 PDF</button>'
            '<p>离线图文说明<br>点击截图可放大<br>指令可一键复制</p></aside><main>'
            '<div class="eyebrow">TEACHER GUIDE · 教师上手指南</div>' + body +
            '<p class="toplink"><a href="#top">返回顶部 ↑</a></p></main></div>'
            '<dialog aria-label="放大查看截图"><button type="button">关闭 ×</button><img alt=""></dialog>'
            '<script>' + SCRIPT + '</script></body></html>')
    target = ROOT / 'templates/local-bank-starter/先看这里.html'
    target.write_text(html, encoding='utf-8')
    print(f'Built offline guide: {len(names)} screenshots, {len(html.encode("utf-8"))} bytes')


if __name__ == '__main__':
    build()
