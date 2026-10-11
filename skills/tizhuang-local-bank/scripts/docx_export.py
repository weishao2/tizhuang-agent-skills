"""Offline editable Word papers from the same frozen question snapshot as HTML."""
from io import BytesIO
from pathlib import Path
import re

from docx import Document
from docx.shared import Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from lxml import etree, html
from PIL import Image
import mathml2omml


def font(style, size):
    style.font.name = 'Times New Roman'
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.font.underline = False
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    for attribute in list(fonts.attrib):
        if 'theme' in attribute.lower():
            del fonts.attrib[attribute]
    fonts.set(qn('w:eastAsia'), '宋体')
    for border in style.element.xpath('./w:pPr/w:pBdr'):
        border.getparent().remove(border)


class ContentWriter:
    """Convert sanitized question HTML, never opening arbitrary paths or URLs."""
    def __init__(self, document, bank, question):
        self.document = document
        self.bank = bank
        self.question = question
        self.assets = {a['path']: a for a in question['assets']}
        self.paragraph = None
        self.container = document
        self.width_mm = 174

    def paragraph_for_inline(self):
        if self.paragraph is None:
            self.paragraph = self.container.add_paragraph()
        return self.paragraph

    def text(self, value, styles):
        if not value:
            return
        # Collapse layout whitespace, keeping nonbreaking answer-space runs.
        value = re.sub(r'[ \t\r\n\f\v]+', ' ', value)
        if not value.strip() and self.paragraph is None:
            return
        run = self.paragraph_for_inline().add_run(value)
        for key, enabled in styles.items():
            if key in ('superscript', 'subscript', 'strike'):
                setattr(run.font, key, enabled)
            else:
                setattr(run, key, enabled)

    def picture(self, node):
        import local_bank as lb
        import ui_layout as ui
        source = node.get('src', '')
        asset = self.assets.get(source)
        if not asset:
            raise ValueError('Word 图片未登记在题目附件中，请重新保存题目')
        data = ui.asset_path(self.bank.root, source).read_bytes()
        if lb.digest(data) != asset['sha256']:
            raise ValueError('Word 图片校验失败')
        try:
            with Image.open(BytesIO(data)) as picture:
                w, h = picture.size
                default_dpi = 144 if self.question.get('source', {}).get('provider') == 'local-pdf' else 96
                dpi = picture.info.get('dpi', (default_dpi, default_dpi))[0]
                if not isinstance(dpi, (int, float)) or not 36 <= dpi <= 1200:
                    dpi = default_dpi
                # Word cannot read WebP; embed a lossless PNG with original colours.
                normalized = BytesIO()
                picture.convert('RGBA' if 'A' in picture.getbands() else 'RGB').save(normalized, format='PNG')
            width = min(self.width_mm, w * 25.4 / dpi, 215 * w / h)
            height = width * h / w
            paragraph = self.paragraph_for_inline()
            run = paragraph.add_run()
            if height > 12 and (paragraph.text or paragraph._p.xpath('.//w:drawing')):
                run.add_break()
            shape = run.add_picture(BytesIO(normalized.getvalue()), width=Mm(width))
            shape._inline.docPr.set('descr', node.get('alt', '题图'))
            if height > 12:
                run.add_break()
        except Exception as exc:
            raise ValueError('Word 无法嵌入题图，请检查图片格式或文件内容') from exc

    def formula(self, node):
        # MathML is generated and sanitized locally; no external DTD or entity fetch.
        source = etree.tostring(node, encoding='unicode', with_tail=False)
        try:
            result = mathml2omml.convert(source)
            root = parse_xml('<root xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + result + '</root>')
            self.paragraph_for_inline()._p.extend(list(root))
        except Exception as exc:
            raise ValueError('公式无法转为 Word 公式，请检查原题公式；未生成不完整试卷') from exc

    def table(self, node):
        rows = node.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')
        if not rows:
            return
        # Keep merged cells faithful; reject unsupported spans instead of losing data.
        if any(c.get('colspan', '1') != '1' or c.get('rowspan', '1') != '1' for row in rows for c in row):
            raise ValueError('Word 暂不支持题目中的合并表格单元格，请整理表格后重试')
        columns = max(len(row.xpath('./td|./th')) for row in rows)
        if not columns:
            return
        table = self.container.add_table(rows=len(rows), cols=columns)
        table.autofit = False
        table.style = 'Table Grid'
        for column in table.columns:
            column.width = Mm(self.width_mm / columns)
        borders = OxmlElement('w:tblBorders')
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            border = OxmlElement('w:' + side)
            for key, value in [('val','single'), ('sz','4'), ('color','D9D9D9')]:
                border.set(qn('w:' + key), value)
            borders.append(border)
        table._tbl.tblPr.append(borders)
        old_container, old_width = self.container, self.width_mm
        for i, row in enumerate(rows):
            for j, cell in enumerate(row.xpath('./td|./th')):
                self.container = table.cell(i, j)
                self.width_mm = old_width / columns - 4
                self.paragraph = self.container.paragraphs[0]
                self.children(cell, {'bold': True} if cell.tag == 'th' else {})
                if cell.tag == 'th':
                    shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), 'F2F2F2')
                    self.container._tc.get_or_add_tcPr().append(shade)
            if all(c.tag == 'th' for c in row):
                table.rows[i]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        self.container, self.width_mm, self.paragraph = old_container, old_width, None

    def children(self, node, styles):
        self.text(node.text, styles)
        for child in node:
            self.node(child, styles)
            self.text(child.tail, styles)

    def node(self, node, styles):
        tag = str(node.tag).split('}')[-1].lower()
        if tag == 'math':
            self.formula(node)
        elif tag == 'img':
            self.picture(node)
        elif tag == 'table':
            self.paragraph = None
            self.table(node)
        elif tag == 'br':
            self.paragraph_for_inline().add_run().add_break()
        elif tag == 'hr':
            self.paragraph = None
        elif tag in ('p', 'div', 'blockquote', 'pre', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li'):
            self.paragraph = None
            if tag == 'li':
                parent = node.getparent()
                prefix = str(list(parent).index(node) + 1) + '. ' if parent.tag == 'ol' else '• '
                self.text(prefix, styles)
            self.children(node, styles)
            self.paragraph = None
        else:
            attribute = {'strong':'bold', 'b':'bold', 'em':'italic', 'i':'italic', 'u':'underline', 's':'strike', 'sup':'superscript', 'sub':'subscript'}.get(tag)
            self.children(node, {**styles, **({attribute: True} if attribute else {})})

    def write(self, content, fmt, context=''):
        import local_bank as lb
        if content.strip():
            try:
                root = html.fragment_fromstring(lb.render(content, fmt), create_parent='div')
                self.paragraph = None
                self.children(root, {})
            except ValueError as exc:
                if context:
                    raise ValueError(f'{context}：{exc}') from exc
                raise


def export_docx(bank, manifest, destination, teacher=False, answer_space_mm=25):
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = Mm(17)
    section.left_margin = section.right_margin = Mm(18)
    section.header_distance = section.footer_distance = Mm(8)
    for name, size in [('Normal',11), ('Title',20), ('Heading 1',12), ('Heading 2',11)]:
        font(document.styles[name], size)
    normal = document.styles['Normal'].paragraph_format
    normal.space_after = Pt(5)
    normal.line_spacing = 1.2
    normal.widow_control = True
    title = document.add_paragraph(manifest['title'], 'Title')
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(8)
    meta = document.add_paragraph('教师答案版' if teacher else '无答案试卷')
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    duration = manifest.get('duration_minutes')
    line = (f'考试时间：{duration} 分钟　　' if duration else '') + f'满分：{manifest["total_score"]:g} 分　　共 {len(manifest["items"])} 题'
    meta = document.add_paragraph(line); meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if not teacher:
        p = document.add_paragraph('姓名：________________　　班级：________________')
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run('第 ')
    field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)
    footer.add_run(' 页')
    for item in manifest['items']:
        q = item['question']
        label = document.add_paragraph(f'{item["number"]}. （{item["score"]:g} 分）', 'Heading 1')
        label.paragraph_format.space_before = Pt(10)
        label.paragraph_format.space_after = Pt(4)
        label.paragraph_format.keep_with_next = True
        writer = ContentWriter(document, bank, q)
        writer.write(q['content'], q['content_format'], f'第 {item["number"]} 题 · 题干')
        if teacher:
            document.add_paragraph('答案', 'Heading 2')
            writer.write(q['answer'] or '原题未提供答案', q['content_format'], f'第 {item["number"]} 题 · 答案')
            if q['analysis'].strip():
                document.add_paragraph('解析', 'Heading 2')
                writer.write(q['analysis'], q['content_format'], f'第 {item["number"]} 题 · 解析')
        elif answer_space_mm:
            p = document.add_paragraph()
            p.paragraph_format.space_after = Mm(answer_space_mm)
            p.paragraph_format.line_spacing = 1
            p.add_run().font.size = Pt(1)
    document.core_properties.title = manifest['title']
    document.core_properties.subject = '教师答案版' if teacher else '无答案试卷'
    document.core_properties.author = '题庄本地题库'
    document.core_properties.comments = ''
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    document.save(str(destination))
