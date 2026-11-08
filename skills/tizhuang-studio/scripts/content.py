"""HTML/MathML renderer adapted from the existing plugin skill; independent copy."""
import html,re,uuid,hashlib
from html.parser import HTMLParser
import markdown
from latex2mathml.converter import convert as mathml
from pathlib import Path

def digest(data): return hashlib.sha256(data).hexdigest()

def asset_path(root, source):
    if not re.fullmatch(r"Assets/[a-f0-9]{64}\.(?:png|jpg|jpeg|gif|webp)",source):
        raise ValueError("附件路径无效")
    p=(Path(root)/source).resolve()
    if Path(root).resolve() not in p.parents: raise ValueError("附件越界")
    return p

class SafeHTML(HTMLParser):
    tags = {"p", "br", "div", "span", "strong", "b", "em", "i", "u", "s", "sub", "sup", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th", "blockquote", "pre", "code", "hr", "img", "a", "h1", "h2", "h3", "h4", "math", "mrow", "mi", "mn", "mo", "mfrac", "msup", "msub", "msqrt", "mtext", "semantics", "annotation", "msubsup", "mroot", "munder", "mover", "munderover", "mtable", "mtr", "mtd", "mstyle", "mspace", "mpadded", "menclose", "mphantom"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.block = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object", "svg"}:
            self.block += 1
        if self.block or tag not in self.tags:
            return
        clean = []
        for key, val in attrs:
            if key in {"alt", "title", "colspan", "rowspan"}:
                clean.append((key, val or ""))
            if tag in self.tags and tag.startswith("m") and key in {"xmlns", "display", "mathvariant", "stretchy", "fence", "separator", "columnalign", "rowalign", "linethickness", "width", "height", "depth", "notation"}:
                clean.append((key, val or ""))
            if (tag == "img" and key == "src") or (tag == "a" and key == "href"):
                v = (val or "").strip()
                if v and not re.match(r"[a-z][a-z0-9+.-]*:", v, re.I) and not v.startswith("//"):
                    clean.append((key, v))
        self.out.append("<" + tag + "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in clean) + ">")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "object", "svg"}:
            self.block = max(0, self.block - 1)
            return
        if not self.block and tag in self.tags:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.block:
            self.out.append(html.escape(data))


def render(text, fmt="markdown"):
    formulas = {}
    def replace_formula(match):
        token = "BANKMATHTOKEN" + uuid.uuid4().hex.upper()
        expression = next(v for v in match.groups() if v is not None)
        # Website Markdown escapes literal answer brackets like \[ NBSP \].
        # An empty answer space is not a formula; preserve its visible brackets
        # and whitespace instead of passing it to the TeX converter.
        if not expression.strip():
            brackets = ("[", "]") if match[0].startswith("\\[") else ("(", ")") if match[0].startswith("\\(") else ("", "")
            formulas[token] = html.escape(brackets[0] + expression + brackets[1])
            return token
        try:
            formulas[token] = mathml(html.unescape(expression), display="block" if match[0].startswith(("$$", "\\[")) else "inline")
        except Exception as exc:
            raise ValueError(f"公式无法转换，请检查 LaTeX: {expression[:80]!r}") from exc
        return token
    text = re.sub(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]|\\\((.+?)\\\)|(?<!\\)\$([^$\n]+?)(?<!\\)\$", replace_formula, text, flags=re.S)
    raw = text if fmt == "html" else markdown.markdown(text, extensions=["tables", "fenced_code"])
    for token, formula in formulas.items():
        raw = raw.replace(token, formula)
    parser = SafeHTML()
    parser.feed(raw)
    return "".join(parser.out)

