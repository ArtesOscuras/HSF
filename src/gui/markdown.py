import re
import tkinter as tk
from src.gui import fonts

FG = "#ffffff"

MD_CODE = "#7fd88f"
MD_EMPH = "#e5c07b"
MD_BLOCKQUOTE = "#e5c07b"
MD_LINK = "#56b6c2"
MD_LIST = "#5c9cf5"
MD_ENUM = "#56b6c2"
MD_HR = "#808080"
MD_FENCE = "#888888"
MD_CODEBLOCK_BG = "#1e1e1e"
MD_TABLE = "#888888"

_HEADER_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_FENCE_RE = re.compile(r'^(\s*)```')
_HR_RE = re.compile(r'^(\s*)(-{3,}|\*{3,}|_{3,})\s*$')
_BLOCKQUOTE_RE = re.compile(r'^(\s*>\s?)(.*)$')
_BULLET_RE = re.compile(r'^(\s*)([-*+])\s+(.*)$')
_ENUM_RE = re.compile(r'^(\s*)(\d+[.)])\s+(.*)$')
_TABLE_ROW_RE = re.compile(r'^\s*\|')
_MD_TOKEN_RE = re.compile(r'(`[^`]+`|\*\*[^*]+\*\*|(?<!\w)__[^_]+__(?!\w)|\*[^*\s][^*]*\*|(?<!\w)_[^_\s][^_]*_(?!\w)|\[[^\]]+\]\([^)]+\))')

_HEADER_DELTAS = {1: 8, 2: 6, 3: 4, 4: 2, 5: 1, 6: 0}


class MarkdownRenderer:
    def __init__(self, text_widget, font_size=11, named=False):
        self.text = text_widget
        self._font_size = font_size
        self._named = named
        self._in_code_block = False
        self._table_buffer = []
        self.configure_tags()

    def configure_tags(self, font_size=None):
        if font_size is not None:
            self._font_size = font_size
        fs = self._font_size
        if self._named:
            bold_font = fonts.view_font_bold(fs)
        else:
            bold_font = (fonts.family_bold(), fs, "bold")
        self.text.tag_configure("md_bold", font=bold_font, foreground=FG)
        for level, delta in _HEADER_DELTAS.items():
            if self._named:
                h_font = fonts.view_font_bold(fs + delta)
            else:
                h_font = (fonts.family_bold(), fs + delta, "bold")
            self.text.tag_configure(f"md_h{level}", font=h_font, foreground=FG)
        self.text.tag_configure("md_code", foreground=MD_CODE)
        self.text.tag_configure("md_emph", foreground=MD_EMPH)
        self.text.tag_configure("md_blockquote", foreground=MD_BLOCKQUOTE)
        self.text.tag_configure("md_link", foreground=MD_LINK)
        self.text.tag_configure("md_list", foreground=MD_LIST)
        self.text.tag_configure("md_enum", foreground=MD_ENUM)
        self.text.tag_configure("md_hr", foreground=MD_HR)
        self.text.tag_configure("md_fence", foreground=MD_FENCE)
        self.text.tag_configure("md_codeblock", background=MD_CODEBLOCK_BG, foreground=FG)
        self.text.tag_configure("md_table", foreground=MD_TABLE)
        self.text.tag_configure("md_plain", foreground=FG)

    def reset(self):
        self._in_code_block = False
        self._table_buffer = []

    def flush(self):
        if self._table_buffer:
            self._flush_table()

    def render(self, text):
        self.reset()
        for line in text.split("\n"):
            if self.insert_line(line) is not True:
                self.text.insert(tk.END, "\n")
        self.flush()

    def insert_line(self, text):
        stripped = text.rstrip()

        if self._in_code_block:
            m = _FENCE_RE.match(stripped)
            if m:
                self._in_code_block = False
                self.text.insert(tk.END, m.group(1) + "```", "md_fence")
            else:
                self.text.insert(tk.END, text, "md_codeblock")
            return

        m = _FENCE_RE.match(stripped)
        if m:
            self._in_code_block = True
            self.text.insert(tk.END, m.group(1) + "```", "md_fence")
            return

        if _TABLE_ROW_RE.match(stripped):
            self._table_buffer.append(stripped)
            return True

        if self._table_buffer:
            self._flush_table()

        m = _HR_RE.match(stripped)
        if m:
            self.text.insert(tk.END, stripped, "md_hr")
            return

        m = _BLOCKQUOTE_RE.match(stripped)
        if m:
            self.text.insert(tk.END, m.group(1), "md_blockquote")
            self._insert_inline(m.group(2))
            return

        m = _HEADER_RE.match(stripped)
        if m and m.group(2).strip():
            level = min(len(m.group(1)), 6)
            self._insert_inline(m.group(2), base_tag=f"md_h{level}")
            return

        m = _BULLET_RE.match(stripped)
        if m:
            self.text.insert(tk.END, m.group(1), None)
            self.text.insert(tk.END, m.group(2), "md_list")
            self.text.insert(tk.END, " ", None)
            self._insert_inline(m.group(3))
            return

        m = _ENUM_RE.match(stripped)
        if m:
            self.text.insert(tk.END, m.group(1), None)
            self.text.insert(tk.END, m.group(2), "md_enum")
            self.text.insert(tk.END, " ", None)
            self._insert_inline(m.group(3))
            return

        self._insert_inline(text)

    def _insert_inline(self, text, base_tag=None):
        if base_tag is None:
            base_tag = f"color_{id(FG)}"
            self.text.tag_configure(base_tag, foreground=FG)
        for part in _MD_TOKEN_RE.split(text):
            if not part:
                continue
            if part.startswith('`') and part.endswith('`') and len(part) >= 2:
                self.text.insert(tk.END, part[1:-1], "md_code")
            elif part.startswith('**') and part.endswith('**') and len(part) >= 4:
                self.text.insert(tk.END, part[2:-2], "md_bold")
            elif part.startswith('__') and part.endswith('__') and len(part) >= 4:
                self.text.insert(tk.END, part[2:-2], "md_bold")
            elif part.startswith('*') and part.endswith('*') and len(part) >= 2:
                self.text.insert(tk.END, part[1:-1], "md_emph")
            elif part.startswith('_') and part.endswith('_') and len(part) >= 2:
                self.text.insert(tk.END, part[1:-1], "md_emph")
            elif part.startswith('[') and part.endswith(')') and '](' in part:
                self.text.insert(tk.END, part[1:part.index('](')], "md_link")
            else:
                self.text.insert(tk.END, part, base_tag)

    def _flush_table(self):
        rows = self._table_buffer
        self._table_buffer = []
        if not rows:
            return
        parsed = []
        for row in rows:
            inner = row.strip().strip('|')
            parsed.append([c.strip() for c in inner.split('|')])
        ncols = max(len(c) for c in parsed) if parsed else 0
        if ncols == 0:
            return
        sep_idx = None
        for i, cells in enumerate(parsed):
            if cells and all(re.fullmatch(r':?-{1,}:?', c) for c in cells):
                sep_idx = i
                break
        widths = [3] * ncols
        for i, cells in enumerate(parsed):
            if i == sep_idx:
                continue
            for j, c in enumerate(cells):
                if j < ncols:
                    widths[j] = max(widths[j], len(c))
        for i, cells in enumerate(parsed):
            if i == sep_idx:
                line = "\u251c" + "\u253c".join("\u2500" * w for w in widths) + "\u2524"
                self.text.insert(tk.END, line, "md_table")
                self.text.insert(tk.END, "\n")
                continue
            padded = []
            for j in range(ncols):
                c = cells[j] if j < len(cells) else ""
                padded.append(" " + c.ljust(widths[j]) + " ")
            line = "\u2502" + "\u2502".join(padded) + "\u2502"
            self.text.insert(tk.END, line, "md_table")
            self.text.insert(tk.END, "\n")
