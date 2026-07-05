import os
import re
import threading
import tkinter as tk
from src.gui import fonts
from .base import BaseView

MUTED = "#888888"
BRIGHT = "#ffffff"
BG = "#111111"
FG = "#ffffff"
SUCCESS = "#00cc66"
ERR_COLOR = "#f44747"


class FileDetailView(BaseView):
    name = "file_detail"
    description = "File content preview"

    def __init__(self, parent, file_path, title, **kwargs):
        self._file_path = file_path
        self._detail_title = title
        super().__init__(parent, **kwargs)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        self._title_label = tk.Label(
            header, text=self._detail_title,
            font=fonts.view_font_bold(22), fg=BRIGHT, bg="#000000",
        )
        self._title_label.pack(anchor="center")
        self._title_label.bind("<Button-1>",
                               lambda e: self._on_back_click())
        self._title_label.bind("<Enter>",
                               lambda e: self._title_label.config(
                                   font=fonts.view_font_bold_under(22)))
        self._title_label.bind("<Leave>",
                               lambda e: self._title_label.config(
                                   font=fonts.view_font_bold(22)))

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew",
                        padx=(300, 300), pady=(10, 0))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame, bg="#000000", fg=BRIGHT,
            font=fonts.view_font(13), borderwidth=0,
            highlightthickness=0, state=tk.DISABLED,
            cursor="", wrap=tk.NONE,
        )
        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("highlight", background="#444400",
                                foreground=BRIGHT)
        self.text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL,
                                 command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a",
                            activebackground="#555555", width=10,
                            borderwidth=0, highlightthickness=0,
                            elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        btn_frame = tk.Frame(self, bg="#000000")
        btn_frame.grid(row=2, column=0, pady=(15, 15))

        search_btn = tk.Label(
            btn_frame, text="  Search  ", bg="#222222", fg=BRIGHT,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        search_btn.pack(side=tk.LEFT, padx=(0, 10))
        search_btn.bind("<Button-1>", lambda e: self._open_search())
        search_btn.bind("<Enter>", lambda e: search_btn.config(bg="#333333"))
        search_btn.bind("<Leave>", lambda e: search_btn.config(bg="#222222"))

        back_btn = tk.Label(
            btn_frame, text="  \u2190 Back  ", bg="#222222", fg=BRIGHT,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        back_btn.pack(side=tk.RIGHT, padx=(10, 0))
        back_btn.bind("<Button-1>", lambda e: self._on_back_click())
        back_btn.bind("<Enter>", lambda e: back_btn.config(bg="#333333"))
        back_btn.bind("<Leave>", lambda e: back_btn.config(bg="#222222"))

        self._load_preview()

    def _load_preview(self):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        try:
            with open(self._file_path, "r", encoding="utf-8",
                      errors="replace") as f:
                all_lines = f.readlines()
            total = len(all_lines)
            shown = min(total, 100)
            for i in range(shown):
                self.text.insert(tk.END, all_lines[i].rstrip("\n").rstrip("\r") + "\n")
            if total > 100:
                self.text.insert(tk.END, "\n...", "muted")
            size = os.path.getsize(self._file_path)
            if size >= 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            elif size >= 1024:
                size_str = f"{size / 1024:.0f} KB"
            else:
                size_str = f"{size} B"
            self.text.insert(tk.END, f"\n\n({size_str}, {total} lines total)", "muted")
        except Exception:
            self.text.insert(tk.END, "Could not read file.", "muted")
        self.text.configure(state=tk.DISABLED)

    def _open_search(self):
        _SearchDialog(self)

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass


class _SearchDialog(tk.Toplevel):
    MAX_MATCHES = 200
    CONTEXT = 50

    def __init__(self, parent, file_path=None, title=None):
        super().__init__(parent)
        self._parent = parent
        self._file_path = file_path or parent._file_path
        self._lines = []
        self._shown_start = 0
        self._shown_end = 0
        self.title(title or "Search")
        self.geometry("950x700")
        self.minsize(700, 500)
        self.configure(bg=BG)

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        top = tk.Frame(self, bg=BG)
        top.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 0))

        tk.Label(top, text="Search", font=fonts.view_font_bold(12),
                 fg=FG, bg=BG,
                 ).grid(row=0, column=0, sticky="w", columnspan=3)

        search_frame = tk.Frame(top, bg=BG)
        search_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        search_frame.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._on_query_changed())
        self._search_entry = tk.Entry(
            search_frame, textvariable=self._search_var,
            bg="#000000", fg=FG, insertbackground=FG,
            font=fonts.view_font(12), relief=tk.FLAT, borderwidth=0,
            highlightbackground="#333333", highlightthickness=1,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", ipady=4)
        self._search_entry.bind("<Return>", lambda e: self._find_next())

        self._regex_var = tk.BooleanVar(value=False)
        self._regex_var.trace_add("write", lambda *a: self._on_query_changed())
        regex_cb = tk.Checkbutton(
            search_frame, text="Regex", variable=self._regex_var,
            bg=BG, fg=MUTED, selectcolor="#333333",
            font=fonts.view_font(11), activebackground=BG,
            activeforeground=FG,
        )
        regex_cb.grid(row=0, column=1, padx=(10, 4))

        clear_q = tk.Label(search_frame, text="\u00d7", fg=MUTED, bg=BG,
                           font=fonts.view_font_bold(16), cursor="")
        clear_q.grid(row=0, column=2)
        clear_q.bind("<Button-1>", lambda e: self._search_var.set(""))
        clear_q.bind("<Enter>", lambda e: clear_q.config(fg=FG))
        clear_q.bind("<Leave>", lambda e: clear_q.config(fg=MUTED))

        nav_frame = tk.Frame(top, bg=BG)
        nav_frame.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        search_btn = self._make_button(nav_frame, "Search")
        search_btn.pack(side=tk.LEFT)
        search_btn.bind("<Button-1>", lambda e: self._find_next())

        prev_btn = self._make_button(nav_frame, "\u25B2  Prev")
        prev_btn.pack(side=tk.LEFT, padx=(8, 0))
        prev_btn.bind("<Button-1>", lambda e: self._find_prev())

        next_btn = self._make_button(nav_frame, "Next  \u25BC")
        next_btn.pack(side=tk.LEFT, padx=(8, 0))
        next_btn.bind("<Button-1>", lambda e: self._find_next())

        self._match_label = tk.Label(
            nav_frame, text="", fg=MUTED, bg=BG, font=fonts.view_font(11))
        self._match_label.pack(side=tk.LEFT, padx=(16, 0))

        clear_hl = self._make_button(nav_frame, "Clear highlights")
        clear_hl.pack(side=tk.RIGHT)
        clear_hl.bind("<Button-1>", lambda e: self._clear_highlights())

        line_frame = tk.Frame(top, bg=BG)
        line_frame.grid(row=3, column=0, sticky="w", pady=(8, 0))
        tk.Label(line_frame, text="Go to line:", fg=MUTED, bg=BG,
                 font=fonts.view_font(11)).pack(side=tk.LEFT)
        self._line_var = tk.StringVar()
        self._line_entry = tk.Entry(
            line_frame, textvariable=self._line_var,
            bg="#000000", fg=FG, insertbackground=FG,
            font=fonts.view_font(11), relief=tk.FLAT, borderwidth=0,
            highlightbackground="#333333", highlightthickness=1, width=8)
        self._line_entry.pack(side=tk.LEFT, padx=(6, 0), ipady=2)
        self._line_entry.bind("<Return>", lambda e: self._go_line())
        go_btn = self._make_button(line_frame, "Go")
        go_btn.pack(side=tk.LEFT, padx=(6, 0))
        go_btn.bind("<Button-1>", lambda e: self._go_line())

        content_frame = tk.Frame(self, bg=BG)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(10, 0))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        self._text = tk.Text(
            content_frame, bg="#000000", fg=BRIGHT,
            font=fonts.view_font(12), borderwidth=0,
            highlightthickness=0, state=tk.DISABLED,
            cursor="", wrap=tk.NONE)
        self._text.tag_configure("muted", foreground=MUTED)
        self._text.tag_configure("highlight", background="#444400",
                                 foreground=BRIGHT)
        self._text.grid(row=0, column=0, sticky="nsew")

        t_scroll = tk.Scrollbar(content_frame, orient=tk.VERTICAL,
                                command=self._text.yview)
        t_scroll.configure(bg="#333333", troughcolor="#1a1a1a",
                           activebackground="#555555", width=10,
                           borderwidth=0, highlightthickness=0,
                           elementborderwidth=0)
        t_scroll.grid(row=0, column=1, sticky="ns")
        self._text.configure(yscrollcommand=t_scroll.set)

        self._loading = tk.Label(
            content_frame, text="Opening file...", fg=MUTED, bg="#000000",
            font=fonts.view_font(14))
        self._loading.place(relx=0.5, rely=0.5, anchor="center")

        bottom = tk.Frame(self, bg=BG)
        bottom.grid(row=2, column=0, sticky="ew", padx=15, pady=(10, 15))

        close_btn = self._make_button(bottom, "Close")
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Button-1>", lambda e: self._on_close())

        self._matches = []
        self._match_index = -1
        self._last_query = ""
        self._last_regex = False
        self._loaded = False
        self._total = 0
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._load_file)

    def _make_button(self, parent, text):
        btn = tk.Label(parent, text=text, bg="#222222", fg=FG,
                       relief=tk.RAISED, bd=1, padx=14, pady=6,
                       font=fonts.view_font(10), cursor="")
        btn.bind("<Enter>", lambda e: btn.config(bg="#333333"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#222222"))
        return btn

    def _load_file(self):
        def _run():
            try:
                with open(self._file_path, "r", encoding="utf-8",
                          errors="replace") as f:
                    self._lines = f.read().splitlines()
            except Exception:
                self._lines = ["Could not read file."]
            self.after(0, self._on_loaded)
        threading.Thread(target=_run, daemon=True).start()

    def _on_loaded(self):
        self._loading.destroy()
        self._loading = None
        self._total = len(self._lines)
        self._load_window(0)
        self._loaded = True
        self._search_entry.focus()

    def _load_window(self, center_line):
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        start = max(0, center_line - self.CONTEXT)
        end = min(self._total, center_line + self.CONTEXT + 1)
        if start != 0:
            self._text.insert(tk.END, "...\n", "muted")
        for i in range(start, end):
            self._text.insert(tk.END, self._lines[i] + "\n")
        if end < self._total:
            self._text.insert(tk.END, "\n...", "muted")
        self._text.insert(tk.END,
                          f"\n\n(Lines {start+1:,}\u2013{min(end, self._total):,} "
                          f"of {self._total:,})", "muted")
        size = os.path.getsize(self._file_path)
        if size >= 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = f"{size} B"
        self._text.insert(tk.END, f"\n({size_str})", "muted")
        self._text.configure(state=tk.DISABLED)
        self._shown_start = start
        self._shown_end = end

    def _on_query_changed(self):
        self._matches = []
        self._match_index = -1
        self._last_query = ""
        self._last_regex = False
        self._match_label.config(text="")

    def _on_close(self):
        self._clear_highlights()
        self.destroy()

    def _clear_highlights(self):
        if not self._loaded:
            return
        self._text.configure(state=tk.NORMAL)
        self._text.tag_remove("highlight", "1.0", tk.END)
        self._text.configure(state=tk.DISABLED)
        self._matches = []
        self._match_index = -1
        self._match_label.config(text="")

    def _find_all_matches(self, query):
        self._matches = []
        use_regex = self._regex_var.get()
        self._last_query = query
        self._last_regex = use_regex
        if use_regex:
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error:
                self._match_label.config(text="Invalid regex", fg=ERR_COLOR)
                return 0
            for line_num in range(self._total):
                if len(self._matches) >= self.MAX_MATCHES:
                    break
                line = self._lines[line_num]
                for m in pattern.finditer(line):
                    if len(self._matches) >= self.MAX_MATCHES:
                        break
                    self._matches.append((line_num, m.start(), m.end()))
        else:
            qlower = query.lower()
            for line_num in range(self._total):
                if len(self._matches) >= self.MAX_MATCHES:
                    break
                line = self._lines[line_num]
                search_in = line.lower()
                col = 0
                while True:
                    col = search_in.find(qlower, col)
                    if col < 0:
                        break
                    if len(self._matches) >= self.MAX_MATCHES:
                        break
                    self._matches.append((line_num, col, col + len(query)))
                    col += 1
        return len(self._matches)

    def _highlight_position(self, index):
        if not self._loaded:
            return
        if 0 <= index < len(self._matches):
            line_num, col_start, col_end = self._matches[index][:3]
            if (line_num < self._shown_start
                    or line_num >= self._shown_end):
                self._load_window(line_num)
            offset = 2 if self._shown_start != 0 else 1
            tag_start = "%d.%d" % (line_num - self._shown_start + offset, col_start)
            tag_end = "%s + %dc" % (tag_start, col_end - col_start)
            self._text.configure(state=tk.NORMAL)
            self._text.tag_remove("highlight", "1.0", tk.END)
            self._text.tag_add("highlight", tag_start, tag_end)
            self._text.see(tag_start)
            self._text.configure(state=tk.DISABLED)

    def _show_status(self):
        count = len(self._matches)
        if count == 0:
            self._match_label.config(text="No matches", fg=ERR_COLOR)
        else:
            self._match_label.config(text="%d of %d" % (self._match_index + 1, count),
                                     fg=SUCCESS)

    def _ensure_fresh(self):
        if not self._loaded:
            return False
        query = self._search_var.get().strip()
        use_regex = self._regex_var.get()
        if not query:
            return False
        if (query != self._last_query or use_regex != self._last_regex
                or not self._matches):
            count = self._find_all_matches(query)
            if count == 0:
                self._match_label.config(text="No matches", fg=ERR_COLOR)
                return False
            self._match_index = 0
        return True

    def _find_next(self):
        if not self._ensure_fresh():
            return
        self._match_index = (self._match_index + 1) % len(self._matches)
        self._highlight_position(self._match_index)
        self._show_status()

    def _find_prev(self):
        if not self._ensure_fresh():
            return
        self._match_index = (self._match_index - 1) % len(self._matches)
        self._highlight_position(self._match_index)
        self._show_status()

    def _go_line(self):
        if not self._loaded:
            return
        try:
            n = int(self._line_var.get())
        except ValueError:
            return
        if n < 1 or n > self._total:
            return
        line_idx = n - 1
        if line_idx < self._shown_start or line_idx >= self._shown_end:
            self._load_window(line_idx)
        self._text.configure(state=tk.NORMAL)
        self._text.tag_remove("highlight", "1.0", tk.END)
        self._text.configure(state=tk.DISABLED)
        offset = 2 if self._shown_start != 0 else 1
        self._text.see("%d.0" % (line_idx - self._shown_start + offset))
        self._match_label.config(text="Line %d" % n, fg=SUCCESS)


def open_file_search(parent, file_path, title="Search"):
    return _SearchDialog(parent, file_path=file_path, title=title)
