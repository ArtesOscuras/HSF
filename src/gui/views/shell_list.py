import os
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from .base import BaseView
from .nav import build as build_nav
from src.shells import shell_db

MUTED = "#888888"
BRIGHT = "#ffffff"
INFO = "#5ba3ec"

ICON_SIZE = 50
COL_GAP = "   "

_icon = None
_delete_img = None


def _load_icon():
    global _icon
    if _icon is not None:
        return _icon
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons", "shells.png")
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


class ShellListView(BaseView):
    name = "shells"
    description = "Reverse shell sessions"

    MIN_NAME = 10

    def _build_ui(self):
        _load_icon()
        _load_delete_img()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        nav_frame = tk.Frame(header, bg="#000000")
        nav_frame.pack(pady=(0, 10))

        build_nav(header, "shells", self.master)

        tk.Label(
            header,
            text="Shells",
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
        sid = item["id"]
        ip = item["ip"]
        stype = item.get("type", "Revershell")
        status = item["status"]
        status_color = "info" if status == "connected" else "muted"

        self.text.insert(tk.END, center_pad, "bright")

        id_tag = f"s_{sid}"
        self.text.tag_configure(id_tag, underline=False)
        self.text.insert(tk.END, f"#{sid}", ("bright", id_tag))
        self.text.tag_bind(id_tag, "<Button-1>", lambda e, s=sid: (
            self._on_shell_click and self._on_shell_click(s)))
        self.text.tag_bind(id_tag, "<Enter>", lambda e, t=id_tag: self.text.tag_configure(t, underline=True))
        self.text.tag_bind(id_tag, "<Leave>", lambda e, t=id_tag: self.text.tag_configure(t, underline=False))

        self.text.insert(tk.END, "\t", "bright")

        icon = _load_icon()
        if icon:
            self.text.image_create(tk.END, image=icon)
        else:
            self.text.insert(tk.END, "#")

        self.text.insert(tk.END, "\t", "bright")

        ip_tag = f"ip_{sid}"
        self.text.tag_configure(ip_tag, underline=False)
        self.text.insert(tk.END, f"{ip}", ("bright", ip_tag))
        self.text.tag_bind(ip_tag, "<Button-1>", lambda e, s=sid: (
            self._on_shell_click and self._on_shell_click(s)))
        self.text.tag_bind(ip_tag, "<Enter>", lambda e, t=ip_tag: self.text.tag_configure(t, underline=True))
        self.text.tag_bind(ip_tag, "<Leave>", lambda e, t=ip_tag: self.text.tag_configure(t, underline=False))

        self.text.insert(tk.END, "\t", "bright")
        self.text.insert(tk.END, f"{stype}", "muted")
        self.text.insert(tk.END, "\t", "bright")
        self.text.insert(tk.END, f"{status}", status_color)
        self.text.insert(tk.END, "\t", "bright")

        del_img = _load_delete_img()
        if del_img:
            self.text.image_create(tk.END, image=del_img)
            del_tag = f"del_{sid}"
            self.text.tag_add(del_tag, "end-2c", "end-1c")
            self.text.tag_bind(del_tag, "<Button-1>", lambda e, s=sid: (
                self._delete_shell(s), "break")[-1])

        self.text.insert(tk.END, "\n", "bright")

    def _delete_shell(self, sid):
        shell_db.close_session(sid)

    def _poll(self):
        items = shell_db.get_all()
        self._items = items

        current_hash = hash(tuple((i["id"], i["status"], i.get("type", ""), i.get("os", "")) for i in items))
        if current_hash == self._last_hash and self.text.index("end-1c") != "1.0":
            self._poll_id = self.after(2000, self._poll)
            return
        self._last_hash = current_hash

        w_id = 4
        w_ip = 12
        w_type = 10
        w_status = 12
        for item in items:
            w_ip = max(w_ip, len(item["ip"]))
            w_type = max(w_type, len(item.get("type", "Revershell")))
            w_status = max(w_status, len(item["status"]))

        font = tkfont.Font(font=self.text.cget("font"))
        gap_px = font.measure(COL_GAP)
        char_w = font.measure(" ")

        def col_w(n):
            return font.measure(" " * n)

        row_content_px = col_w(w_id) + gap_px + ICON_SIZE + gap_px + col_w(w_ip) + gap_px + col_w(w_type) + gap_px + col_w(w_status)

        w = self.text.winfo_width()
        if w > row_content_px:
            pad_chars = int((w - row_content_px) // 2 // char_w)
            center_pad = " " * max(0, pad_chars)
        else:
            center_pad = "  "

        center_px = font.measure(center_pad)
        tabs = []
        t = center_px + col_w(w_id) + gap_px
        tabs.append(t)
        t += ICON_SIZE + gap_px
        tabs.append(t)
        t += col_w(w_ip) + gap_px
        tabs.append(t)
        t += col_w(w_type) + gap_px
        tabs.append(t)

        self.text.configure(tabs=tabs)

        scroll_pos = self.text.yview()[0]

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        if not items:
            self.text.insert(tk.END, "\n", "bright")
            self.text.insert(tk.END, center_pad, "bright")
            self.text.insert(tk.END, "No shells connected yet.\n", "muted")
            self.text.insert(tk.END, center_pad, "bright")
            self.text.insert(tk.END, "Use 'start-listener' to start the listener.\n", "muted")
        else:
            for item in items:
                self._insert_line(item, center_pad)

        self.text.yview_moveto(scroll_pos)
        self.text.configure(state=tk.DISABLED)

        self._poll_id = self.after(2000, self._poll)
