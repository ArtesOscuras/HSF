import os
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from .base import BaseView
from .nav import build as build_nav

MUTED = "#888888"
BRIGHT = "#ffffff"

ICON_SIZE = 50
COL_GAP = "   "

_icons = {}

_ICON_FILES = {
    "scanner": "scanner.png",
    "fuzzer": "fuzzer.png",
    "webrecorder": "webrecorder.png",
}


def _load_tool_icons():
    icons_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons")
    icons_dir = os.path.abspath(icons_dir)
    for action, filename in _ICON_FILES.items():
        if action in _icons:
            continue
        path = os.path.join(icons_dir, filename)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGBA")
                img = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
                _icons[action] = ImageTk.PhotoImage(img)
            except Exception:
                _icons[action] = None
        else:
            _icons[action] = None


def _get_tool_icon(action):
    return _icons.get(action)


class ToolsView(BaseView):
    name = "tools"
    description = "Available tools"

    MIN_NAME = 14

    def _build_ui(self):
        _load_tool_icons()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        nav_frame = tk.Frame(header, bg="#000000")
        nav_frame.pack(pady=(0, 10))

        build_nav(header, "tools", self.master)

        tk.Label(
            header,
            text="Tools",
            font=("Menlo", 22, "bold"),
            fg="#ffffff",
            bg="#000000",
        ).pack(anchor="center")

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            bg="#000000",
            fg=BRIGHT,
            font=("Menlo", 16),
            borderwidth=0,
            highlightthickness=0,
            pady=10,
            state=tk.NORMAL,
            cursor="",
            wrap=tk.NONE,
            spacing1=8,
            spacing3=8,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("bright", foreground=BRIGHT)
        self.text.tag_configure("tool_name", foreground=BRIGHT, font=("Menlo", 18))
        self.text.tag_configure("tool_desc", foreground=MUTED, font=("Menlo", 12))

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        self._tools = [
            {"name": "Scanner", "action": "scanner", "desc": "Scan interface or ip."},
            {"name": "Fuzzer", "action": "fuzzer", "desc": "Fuzz directory or subdommains."},
            {"name": "Webrecorder", "action": "webrecorder", "desc": "Record web evidences for analisis."},
        ]

        self._poll_id = None

    def on_activate(self):
        self.after(100, self._poll)

    def on_deactivate(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _poll(self):
        self._render()
        self._poll_id = self.after(2000, self._poll)

    def _render(self):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        w_name = self.MIN_NAME
        w_desc = 20
        for t in self._tools:
            w_name = max(w_name, len(t["name"]))
            w_desc = max(w_desc, len(t["desc"]))

        font = tkfont.Font(font=("Menlo", 18))
        font_desc = tkfont.Font(font=("Menlo", 12))
        gap_px = font.measure(COL_GAP)
        char_w = font_desc.measure(" ")

        row_content_px = ICON_SIZE + gap_px + font.measure(" " * w_name) + gap_px + font_desc.measure(" " * w_desc)

        w = self.text.winfo_width()
        if w > row_content_px:
            pad_chars = int((w - row_content_px) // 2 // char_w)
            center_pad = " " * max(0, pad_chars)
        else:
            center_pad = "  "

        center_px = font.measure(center_pad)
        tabs = []
        t = center_px + ICON_SIZE + gap_px
        tabs.append(t)
        t += font.measure(" " * w_name) + gap_px
        tabs.append(t)

        self.text.configure(tabs=tabs)

        for tool in self._tools:
            self._insert_tool(tool, center_pad)

        self.text.configure(state=tk.DISABLED)

    def _insert_tool(self, tool, center_pad):
        name = tool["name"]
        action = tool["action"]

        self.text.insert(tk.END, center_pad, "bright")

        icon = _get_tool_icon(action)
        if icon:
            self.text.image_create(tk.END, image=icon)
        else:
            self.text.insert(tk.END, "?")

        tag = f"tool_{name}"
        self.text.tag_configure(tag, underline=False)

        self.text.insert(tk.END, "\t", "bright")
        self.text.insert(tk.END, name, ("tool_name", tag))
        self.text.tag_bind(tag, "<Button-1>", lambda e, t=tool: (
            self._on_tool_click and self._on_tool_click(t["action"])))
        self.text.tag_bind(tag, "<Enter>", lambda e, t=tag: self.text.tag_configure(t, underline=True))
        self.text.tag_bind(tag, "<Leave>", lambda e, t=tag: self.text.tag_configure(t, underline=False))

        self.text.insert(tk.END, "\t", "bright")
        self.text.insert(tk.END, tool["desc"], "tool_desc")

        self.text.insert(tk.END, "\n", "bright")
