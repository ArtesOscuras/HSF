import os
import shutil
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from .base import BaseView

MUTED = "#888888"
BRIGHT = "#ffffff"
INFO = "#5ba3ec"

ICON_SIZE = 50
COL_GAP = "   "

_icon = None


def _load_icon():
    global _icon
    if _icon is not None:
        return _icon
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons", "evidence.png")
    path = os.path.abspath(path)
    if os.path.isfile(path):
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
            _icon = ImageTk.PhotoImage(img)
        except Exception:
            _icon = False
    else:
        _icon = False
    return _icon


_delete_img = None


def _load_delete_img():
    global _delete_img
    if _delete_img is not None:
        return _delete_img
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons", "delete.png")
    path = os.path.abspath(path)
    if os.path.isfile(path):
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((20, 20), Image.LANCZOS)
            _delete_img = ImageTk.PhotoImage(img)
        except Exception:
            _delete_img = False
    else:
        _delete_img = False
    return _delete_img


def _get_evidence_dir():
    base = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    return os.path.abspath(base)


def _list_evidences():
    base = _get_evidence_dir()
    result = []
    if os.path.isdir(base):
        for entry in sorted(os.listdir(base)):
            entry_path = os.path.join(base, entry)
            if os.path.isdir(entry_path):
                session_path = os.path.join(entry_path, "session.json")
                if os.path.isfile(session_path):
                    try:
                        import json
                        with open(session_path) as f:
                            meta = json.load(f)
                        req_count = meta.get("request_count", 0)
                    except Exception:
                        req_count = 0
                    result.append({"name": entry, "requests": req_count})
    return result


class EvidenceListView(BaseView):
    name = "evidences"
    description = "Recorded evidence sessions"

    MIN_NAME = 15

    def _nav_btn(self, text, view_name, parent, active):
        btn = tk.Label(
            parent, text=f"  {text}  ",
            font=("Menlo", 11, "bold") if active else ("Menlo", 11),
            fg="#ffffff" if active else "#888888",
            bg="#000000",
        )
        btn.pack(side=tk.LEFT, padx=5)
        btn.bind("<Button-1>", lambda e: self.master.activate_view(view_name))
        btn.bind("<Enter>", lambda e: btn.config(font=("Menlo", 11, "bold", "underline") if active else ("Menlo", 11, "underline")))
        btn.bind("<Leave>", lambda e: btn.config(font=("Menlo", 11, "bold") if active else ("Menlo", 11)))

    def _build_ui(self):
        _load_icon()
        _load_delete_img()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        nav_frame = tk.Frame(header, bg="#000000")
        nav_frame.pack(pady=(0, 10))

        self._nav_btn("Tools", "tools", nav_frame, False)
        self._nav_btn("Machines", "machines", nav_frame, False)
        self._nav_btn("Domains", "domains", nav_frame, False)
        self._nav_btn("Evidences", "evidences", nav_frame, True)
        self._nav_btn("Credentials", "credentials", nav_frame, False)

        tk.Label(
            header,
            text="Evidence",
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
            state=tk.DISABLED,
            cursor="",
            wrap=tk.NONE,
            spacing1=8,
            spacing3=8,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("bright", foreground=BRIGHT)
        self.text.tag_configure("info", foreground=INFO)

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        self._last_hash = None
        self._poll_id = None

    def on_activate(self):
        self.after(100, self._poll)

    def on_deactivate(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self._items = []

    def _insert_line(self, item, center_pad):
        name = item["name"]
        reqs = item["requests"]
        req_text = f"{reqs} requests"

        self.text.insert(tk.END, center_pad, "bright")

        icon = _load_icon()
        if icon:
            self.text.image_create(tk.END, image=icon)
        else:
            self.text.insert(tk.END, "?")
        self.text.insert(tk.END, "\t", "bright")

        tag = f"e_{name}"
        self.text.tag_configure(tag, underline=False)
        self.text.insert(tk.END, name[:50] + "\u2026" if len(name) > 50 else name, ("bright", tag))
        self.text.tag_bind(tag, "<Button-1>", lambda e, n=name: (
            self._on_item_click and self._on_item_click(n)))
        self.text.tag_bind(tag, "<Enter>", lambda e, t=tag: self.text.tag_configure(t, underline=True))
        self.text.tag_bind(tag, "<Leave>", lambda e, t=tag: self.text.tag_configure(t, underline=False))
        self.text.insert(tk.END, "\t", "bright")

        self.text.insert(tk.END, req_text, "muted")
        self.text.insert(tk.END, "\t", "bright")

        del_img = _load_delete_img()
        if del_img:
            self.text.image_create(tk.END, image=del_img)
            del_tag = f"del_{name}"
            self.text.tag_add(del_tag, "end-2c", "end-1c")
            self.text.tag_bind(del_tag, "<Button-1>", lambda e, n=name: (
                self._delete_evidence(n), "break")[-1])

        self.text.insert(tk.END, "\n", "muted")

    @staticmethod
    def _delete_evidence(name):
        base = _get_evidence_dir()
        path = os.path.join(base, name)
        if os.path.isdir(path):
            shutil.rmtree(path)

    def _poll(self):
        items = _list_evidences()
        self._items = items

        current_hash = hash(tuple((i["name"], i["requests"]) for i in items))
        if current_hash == self._last_hash and self.text.index("end-1c") != "1.0":
            self._poll_id = self.after(2000, self._poll)
            return
        self._last_hash = current_hash

        w_name = self.MIN_NAME
        w_reqs = 10
        for item in items:
            w_name = max(w_name, len(item["name"]))
            w_reqs = max(w_reqs, len(f"{item['requests']} requests"))

        font = tkfont.Font(font=self.text.cget("font"))
        gap_px = font.measure(COL_GAP)
        char_w = font.measure(" ")

        def col_w(n):
            return font.measure(" " * n)

        row_content_px = ICON_SIZE + gap_px + col_w(w_name) + gap_px + col_w(w_reqs) + gap_px + col_w(3)

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
        t += col_w(w_name) + gap_px
        tabs.append(t)
        t += col_w(w_reqs) + gap_px
        tabs.append(t)

        self.text.configure(tabs=tabs)

        scroll_pos = self.text.yview()[0]

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        if not items:
            self.text.insert(tk.END, "\n", "bright")
            self.text.insert(tk.END, center_pad, "bright")
            self.text.insert(tk.END, "No evidence sessions recorded yet.\n", "muted")
        else:
            for item in items:
                self._insert_line(item, center_pad)

        self.text.yview_moveto(scroll_pos)
        self.text.configure(state=tk.DISABLED)

        self._poll_id = self.after(2000, self._poll)
