import os
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from .base import BaseView
from src.machines import credential_db

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
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons", "credential.png")
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


class CredentialListView(BaseView):
    name = "credentials"
    description = "Stored credentials"

    MIN_NAME = 10

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
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        nav_frame = tk.Frame(header, bg="#000000")
        nav_frame.pack(pady=(0, 10))
        self._nav_btn("Machines", "machines", nav_frame, False)
        self._nav_btn("Domains", "domains", nav_frame, False)
        self._nav_btn("Evidences", "evidences", nav_frame, False)
        self._nav_btn("Credentials", "credentials", nav_frame, True)

        tk.Label(
            header, text="Credentials",
            font=("Menlo", 22, "bold"), fg="#ffffff", bg="#000000",
        ).pack(anchor="center")

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            bg="#000000", fg=BRIGHT,
            font=("Menlo", 16), borderwidth=0, highlightthickness=0,
            pady=10, state=tk.DISABLED, cursor="",
            wrap=tk.NONE, spacing1=8, spacing3=8,
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

        btn_frame = tk.Frame(self, bg="#000000")
        btn_frame.grid(row=2, column=0, pady=(15, 15))

        usr_btn = tk.Label(
            btn_frame, text="  Users / Passwords  ", bg="#222222", fg=BRIGHT,
            font=("Menlo", 12), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        usr_btn.pack(side=tk.LEFT, padx=(0, 10))

        hash_btn = tk.Label(
            btn_frame, text="  Hashes  ", bg="#222222", fg=BRIGHT,
            font=("Menlo", 12), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        hash_btn.pack(side=tk.LEFT)

        usr_btn.bind("<Button-1>", lambda e: self.master.activate_view("user-pass"))
        usr_btn.bind("<Enter>", lambda e: usr_btn.config(bg="#333333"))
        usr_btn.bind("<Leave>", lambda e: usr_btn.config(bg="#222222"))
        hash_btn.bind("<Button-1>", lambda e: self.master.activate_view("hashes"))
        hash_btn.bind("<Enter>", lambda e: hash_btn.config(bg="#333333"))
        hash_btn.bind("<Leave>", lambda e: hash_btn.config(bg="#222222"))

        self._last_hash = None
        self._poll_id = None

    def on_activate(self):
        self.after(100, self._poll)

    def on_deactivate(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self._items = []

    def _insert_line(self, item, w_name, w_pass, center_pad):
        user = item.get("username", "") or ""
        pwd = item.get("password", "") or item.get("hash_nt", "") or ""

        self.text.insert(tk.END, center_pad, "bright")

        icon = _load_icon()
        if icon:
            self.text.image_create(tk.END, image=icon)
        else:
            self.text.insert(tk.END, "?")
        self.text.insert(tk.END, "\t", "bright")

        tag = f"cred_{item['id']}"
        self.text.tag_configure(tag, underline=False)
        self.text.insert(tk.END, user[:40] + "\u2026" if len(user) > 40 else user, ("bright", tag))
        self.text.tag_bind(tag, "<Button-1>", lambda e, cid=item["id"]: (
            self._on_cred_click and self._on_cred_click(cid)))
        self.text.tag_bind(tag, "<Enter>", lambda e, t=tag: self.text.tag_configure(t, underline=True))
        self.text.tag_bind(tag, "<Leave>", lambda e, t=tag: self.text.tag_configure(t, underline=False))
        self.text.insert(tk.END, "\t", "bright")

        self.text.insert(tk.END, pwd[:16] + "\u2026" if len(pwd) > 16 else pwd, "muted")
        self.text.insert(tk.END, "\t", "bright")

        del_img = _load_delete_img()
        if del_img:
            self.text.image_create(tk.END, image=del_img)
            del_tag = f"delc_{item['id']}"
            self.text.tag_add(del_tag, "end-2c", "end-1c")
            self.text.tag_bind(del_tag, "<Button-1>", lambda e, cid=item["id"]: (
                credential_db.delete_credential(cid), "break")[-1])

        self.text.insert(tk.END, "\n", "bright")

    def _poll(self):
        items = credential_db.load_credentials()
        self._items = items

        current_hash = hash(tuple((i["id"], i.get("username", ""), i.get("password", ""), i.get("hash_nt", "")) for i in items))
        if current_hash == self._last_hash and self.text.index("end-1c") != "1.0":
            self._poll_id = self.after(2000, self._poll)
            return
        self._last_hash = current_hash

        w_name = self.MIN_NAME
        w_pass = 8
        for item in items:
            user = item.get("username", "") or ""
            w_name = max(w_name, len(user))
            pwd = item.get("password", "") or item.get("hash_nt", "") or ""
            w_pass = max(w_pass, min(len(pwd), 17))

        font = tkfont.Font(font=self.text.cget("font"))
        gap_px = font.measure(COL_GAP)
        char_w = font.measure(" ")

        def col_w(n):
            return font.measure(" " * n)

        row_content_px = ICON_SIZE + gap_px + col_w(w_name) + gap_px + col_w(w_pass) + char_w + 20

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
        t += col_w(w_pass) + char_w
        tabs.append(t)

        scroll_pos = self.text.yview()[0]

        self.text.configure(state=tk.NORMAL, tabs=tabs)
        self.text.delete("1.0", tk.END)

        if not items:
            self.text.insert(tk.END, "\n", "bright")
            self.text.insert(tk.END, center_pad, "bright")
            self.text.insert(tk.END, "No credentials stored yet.\n", "muted")
        else:
            for item in items:
                self._insert_line(item, w_name, w_pass, center_pad)

        self.text.yview_moveto(scroll_pos)
        self.text.configure(state=tk.DISABLED)

        self._poll_id = self.after(2000, self._poll)
