"""Offline editable Word papers from the same frozen question snapshot as HTML."""
from io import BytesIO
from pathlib import Path
import re
from paper_layout import groups, needs_space
from content import stem_layout

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
        import content as lb
        import content as ui
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
            width = min(self.width_mm, w * 25.4 / dpi, 150 * w / h)
            height = width * h / w
            paragraph = self.paragraph_for_inline()
            if height > 12 and (paragraph.text or paragraph._p.xpath('.//w:drawing')):
                self.paragraph = None
                paragraph = self.paragraph_for_inline()
            if height > 12:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.space_before = Pt(4)
            run = paragraph.add_run()
            shape = run.add_picture(BytesIO(normalized.getvalue()), width=Mm(width))
            shape._inline.docPr.set('descr', node.get('alt', '题图'))
            if height > 12:
                self.paragraph = None
        except Exception as exc:
            raise ValueError('Word 无法嵌入题图，请检查图片格式或文件内容') from exc

    def formula(self, node):
        # MathML is generated and sanitized locally; no external DTD or entity fetch.
        import copy
        node = copy.deepcopy(node)
        # mathml2omml drops mspace; retain answer spaces such as (\quad).
        for gap in node.iter():
            if str(gap.tag).split('}')[-1] == 'mspace':
                gap.tag = 'mtext'
                gap.attrib.clear()
                gap.text = '\u2003'
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
        import content as lb
        if content.strip():
            try:
                root = html.fragment_fromstring(lb.render(content, fmt), create_parent='div')
                self.paragraph = None
                self.children(root, {})
            except ValueError as exc:
                if context:
                    raise ValueError(f'{context}：{exc}') from exc
                raise


def align_options(paragraph):
    """Align an unambiguous A-D option paragraph without flattening OMML/runs."""
    texts = paragraph._p.xpath('.//w:t|.//m:t')
    text = ''.join(t.text or '' for t in texts)
    matches = list(re.finditer(r'(?:^|\s)([A-D])[.．、]\s*', text))
    if [m.group(1) for m in matches] != list('ABCD') or text[:matches[0].start()].strip():
        return
    lengths = [len(text[m.end():matches[i+1].start() if i < 3 else len(text)].strip()) for i,m in enumerate(matches)]
    # Conservative character widths; long choices retain one choice per line.
    columns = 4 if max(lengths) <= 12 else 2 if max(lengths) <= 26 else 1
    for i in range(1, columns):
        paragraph.paragraph_format.tab_stops.add_tab_stop(Mm(174 * i / columns))
    for node in list(paragraph._p.xpath('.//w:t')):
        value = node.text or ''
        parts = re.split(r'\s+([BCD][.．、]\s*)', value)
        if len(parts) == 1:
            continue
        node.text = parts[0]
        anchor = node
        for i in range(1, len(parts), 2):
            index = ord(parts[i][0]) - ord('A')
            sep = OxmlElement('w:br' if index % columns == 0 else 'w:tab')
            anchor.addnext(sep)
            token = OxmlElement('w:t'); token.set(qn('xml:space'), 'preserve')
            token.text = parts[i] + parts[i+1]
            sep.addnext(token); anchor = token


def has_content(value, fmt):
    import content as lb
    root = html.fragment_fromstring(lb.render(value or '', fmt), create_parent='div')
    return bool(root.text_content().strip() or root.xpath('.//img|.//math'))


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
    if teacher:
        meta = document.add_paragraph('教师答案版')
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
    for group in groups(manifest):
        heading = document.add_paragraph(group['title'], 'Heading 1')
        heading.paragraph_format.space_before = Pt(12)
        heading.paragraph_format.keep_with_next = True
        for item in group['items']:
            q = item['question']
            label = document.add_paragraph()
            label.add_run(f'{item["number"]}. （{item["score"]:g} 分）').bold = True
            label.paragraph_format.space_before = Pt(10)
            label.paragraph_format.space_after = Pt(4)
            label.paragraph_format.keep_with_next = True
            writer = ContentWriter(document, bank, q)
            body_start = len(document.paragraphs)
            writer.write(stem_layout(bank.root, q, paper=True), q['content_format'], f'第 {item["number"]} 题 · 题干')
            # Keep a normal-sized stem and its figure/options on the same page.
            # Word can still split content exceeding a whole page.
            body_paragraphs = document.paragraphs[body_start:]
            # Merge only the first textual body paragraph, never across an initial table/figure.
            if body_paragraphs and label._p.getnext() is body_paragraphs[0]._p and not body_paragraphs[0]._p.xpath('.//w:drawing'):
                first = body_paragraphs.pop(0)
                for child in list(first._p):
                    if child.tag != qn('w:pPr'):
                        label._p.append(child)
                first._p.getparent().remove(first._p)
            body_paragraphs.insert(0, label)
            for index, paragraph in enumerate(body_paragraphs):
                align_options(paragraph)
                paragraph.paragraph_format.keep_together = True
                paragraph.paragraph_format.keep_with_next = index < len(body_paragraphs) - 1
            if teacher:
                document.add_paragraph('答案', 'Heading 2')
                writer.write(q['answer'] if has_content(q['answer'], q['content_format']) else '原题未提供答案', q['content_format'], f'第 {item["number"]} 题 · 答案')
                if has_content(q['analysis'], q['content_format']):
                    document.add_paragraph('解析', 'Heading 2')
                    writer.write(q['analysis'], q['content_format'], f'第 {item["number"]} 题 · 解析')
            elif answer_space_mm and needs_space(q):
                p = document.add_paragraph()
                p.paragraph_format.space_after = Mm(answer_space_mm)
                p.paragraph_format.line_spacing = 1
                p.add_run().font.size = Pt(1)
    document.core_properties.title = manifest['title']
    document.core_properties.subject = '教师答案版' if teacher else '无答案试卷'
    document.core_properties.author = '题庄 2.0'
    document.core_properties.comments = ''
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    document.save(str(destination))
