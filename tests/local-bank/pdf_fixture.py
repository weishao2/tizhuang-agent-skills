"""Deterministic teacher-workflow fixtures, never mixed into the teacher's own vault."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.utils import ImageReader
import pypdfium2


def create(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    text = root / '文字数学试卷.pdf'
    c = canvas.Canvas(str(text), pagesize=(595, 842))
    def line(s, y, x=42):
        c.setFont('STSong-Light', 14)
        c.drawString(x, y, s)
    line('本地题库导入验证（自编样卷）', 788)
    line('1. 计算 2 的三次方，选择正确答案。', 724)
    line('A. 6    B. 8    C. 9    D. 12', 684)
    line('2. 如图，矩形的长为 6，宽为 4。', 584)
    line('（1）求矩形的面积。', 552)
    c.rect(95, 340, 180, 120)
    line('6', 472, 178)
    line('4', 395, 73)
    line('第 2 题还有下一页的小问。', 266)
    c.showPage()
    line('（2）接上一页，求这个矩形的周长。', 766)
    line('3. 已知一次函数 y = 2x + 1，求 x = 3 时的函数值。', 646)
    line('请写出代入计算的过程。', 604)
    c.showPage()
    line('参考答案', 788)
    line('1. B。2 的三次方等于 8。', 724)
    line('2. 面积为 24，周长为 20。', 624)
    line('3. 代入 x = 3，得到 y = 7。', 524)
    c.save()
    scan = root / '扫描数学试卷.pdf'
    doc = pypdfium2.PdfDocument(str(text))
    c = canvas.Canvas(str(scan), pagesize=(595, 842))
    for i in range(len(doc)):
        p = doc[i]
        bitmap = p.render(scale=2)
        image = bitmap.to_pil()
        image.save(root / f'原页-{i+1}.png')
        c.drawImage(ImageReader(image), 0, 0, width=595, height=842)
        c.showPage()
        bitmap.close()
        p.close()
    doc.close()
    c.save()
    double = root / '双栏数学试卷.pdf'
    c = canvas.Canvas(str(double), pagesize=(595, 842))
    line('1. 求 1 + 1。', 730, 30)
    line('2. 求 2 + 2。', 730, 330)
    c.save()
    return text, scan, double


if __name__ == '__main__':
    import sys
    create(sys.argv[1])
