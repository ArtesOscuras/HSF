import os
import sqlite3
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
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons", "hashes2.png")
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


class HashListView(BaseView):
    name = "hashes"
    description = "Stored hashes"

    MIN_TYPE = 8
    MIN_HASH = 16

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

        self._title_label = tk.Label(
            header, text="Hashes",
            font=("Menlo", 22, "bold"), fg=BRIGHT, bg="#000000",
        )
        self._title_label.pack(anchor="center")
        self._title_label.bind("<Button-1>", lambda e: self.master.activate_view("credentials"))
        self._title_label.bind("<Enter>", lambda e: self._title_label.config(font=("Menlo", 22, "bold", "underline")))
        self._title_label.bind("<Leave>", lambda e: self._title_label.config(font=("Menlo", 22, "bold")))

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

        back_btn = tk.Label(
            btn_frame, text="  \u2190 Back  ", bg="#222222", fg=BRIGHT,
            font=("Menlo", 12), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        back_btn.pack(side=tk.RIGHT, padx=(10, 0))
        back_btn.bind("<Button-1>", lambda e: self.master.activate_view("credentials"))
        back_btn.bind("<Enter>", lambda e: back_btn.config(bg="#333333"))
        back_btn.bind("<Leave>", lambda e: back_btn.config(bg="#222222"))

        add_btn = tk.Label(
            btn_frame, text="  Add hash  ", bg="#222222", fg=BRIGHT,
            font=("Menlo", 12), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        add_btn.pack(side=tk.LEFT)
        add_btn.bind("<Button-1>", lambda e: self._open_add_hash())
        add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#333333"))
        add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#222222"))

        self._last_hash = None
        self._poll_id = None

    def on_activate(self):
        self.after(100, self._poll)

    def on_deactivate(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self._items = []

    def _insert_line(self, item, w_type, w_hash, center_pad):
        htype = item.get("type", "") or ""
        hval = item.get("hash", "") or ""

        self.text.insert(tk.END, center_pad, "bright")

        icon = _load_icon()
        if icon:
            self.text.image_create(tk.END, image=icon)
        else:
            self.text.insert(tk.END, "?")
        self.text.insert(tk.END, "\t", "bright")

        tag = f"htype_{item['id']}"
        self.text.tag_configure(tag, underline=False)
        self.text.insert(tk.END, htype, ("bright", tag))
        self.text.tag_bind(tag, "<Button-1>", lambda e, hid=item["id"]: (
            self._on_hash_click and self._on_hash_click(hid)))
        self.text.tag_bind(tag, "<Enter>", lambda e, t=tag: self.text.tag_configure(t, underline=True))
        self.text.tag_bind(tag, "<Leave>", lambda e, t=tag: self.text.tag_configure(t, underline=False))
        self.text.insert(tk.END, "\t", "bright")

        self.text.insert(tk.END, hval[:16] + "\u2026" if len(hval) > 16 else hval, "muted")
        self.text.insert(tk.END, "\t", "bright")

        del_img = _load_delete_img()
        if del_img:
            self.text.image_create(tk.END, image=del_img)
            del_tag = f"delh_{item['id']}"
            self.text.tag_add(del_tag, "end-2c", "end-1c")
            self.text.tag_bind(del_tag, "<Button-1>", lambda e, hid=item["id"]: (
                credential_db.delete_hash_entry(hid), "break")[-1])

        self.text.insert(tk.END, "\n", "bright")

    def _poll(self):
        items = credential_db.load_hashes()
        self._items = items

        current_hash = hash(tuple((i["id"], i.get("type", ""), i.get("hash", "")) for i in items))
        if current_hash == self._last_hash and self.text.index("end-1c") != "1.0":
            self._poll_id = self.after(2000, self._poll)
            return
        self._last_hash = current_hash

        w_type = self.MIN_TYPE
        w_hash = self.MIN_HASH
        for item in items:
            w_type = max(w_type, len(item.get("type", "") or ""))
            hval = item.get("hash", "") or ""
            w_hash = max(w_hash, min(len(hval), 17))

        font = tkfont.Font(font=self.text.cget("font"))
        gap_px = font.measure(COL_GAP)
        char_w = font.measure(" ")

        def col_w(n):
            return font.measure(" " * n)

        row_content_px = ICON_SIZE + gap_px + col_w(w_type) + gap_px + col_w(w_hash) + char_w + 20

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
        t += col_w(w_type) + gap_px
        tabs.append(t)
        t += col_w(w_hash) + char_w
        tabs.append(t)

        scroll_pos = self.text.yview()[0]

        self.text.configure(state=tk.NORMAL, tabs=tabs)
        self.text.delete("1.0", tk.END)

        if not items:
            self.text.insert(tk.END, "\n", "bright")
            self.text.insert(tk.END, center_pad, "bright")
            self.text.insert(tk.END, "No hashes stored yet.\n", "muted")
        else:
            for item in items:
                self._insert_line(item, w_type, w_hash, center_pad)

        self.text.yview_moveto(scroll_pos)
        self.text.configure(state=tk.DISABLED)

        self._poll_id = self.after(2000, self._poll)

    def _open_add_hash(self):
        _HashDialog(self)


class _HashDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._sel_type = None

        self.title("Add Hash")
        self.geometry("780x580")
        self.configure(bg="#111111")

        self.transient(parent)
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        tk.Label(
            self, text="Type", font=("Menlo", 11, "bold"),
            fg=MUTED, bg="#111111",
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))

        type_frame = tk.Frame(self, bg="#000000")
        type_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=15, pady=(0, 5))
        type_frame.columnconfigure(0, weight=1)
        type_frame.rowconfigure(0, weight=1)

        self._type_list = tk.Listbox(
            type_frame, bg="#000000", fg="#ffffff",
            selectbackground="#333333", selectforeground="#ffffff",
            font=("Menlo", 11), borderwidth=0, highlightthickness=0,
            activestyle="none", exportselection=False, height=6,
        )
        self._type_list.grid(row=0, column=0, sticky="nsew")
        self._type_list.bind("<<ListboxSelect>>", self._on_type_select)

        scrollbar = tk.Scrollbar(type_frame, orient=tk.VERTICAL, command=self._type_list.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._type_list.configure(yscrollcommand=scrollbar.set)

        self._type_names = []
        self._type_modes = {}
        self._type_examples = {}
        try:
            proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            db_path = os.path.join(proj, "credentials", "hashcat.dbs")
            if os.path.isfile(db_path):
                conn = sqlite3.connect(db_path)
                rows = conn.execute('SELECT "Hash-Mode", "Hash-Name", "Example" FROM DefaultMode ORDER BY "Hash-Mode"').fetchall()
                for mode, name, example in rows:
                    self._type_list.insert(tk.END, f"  {name}")
                    self._type_names.append(name)
                    self._type_modes[name] = str(mode) if mode != -1 else ""
                    self._type_examples[name] = example
                conn.close()
                if self._type_names:
                    self._type_list.selection_set(0)
        except Exception:
            pass

        self._example_label = tk.Label(
            self, text="", font=("Menlo", 9),
            fg=MUTED, bg="#111111", wraplength=600,
        )
        self._example_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(2, 5))

        fields = [
            ("Hash", "hash", ""),
            ("Salt", "salt", ""),
            ("Peper", "peper", ""),
            ("Hashcat mode", "hascat_mode", ""),
            ("Origin", "origin_obteined", "Added manually by user"),
        ]

        row = 3
        for label, key, default in fields:
            tk.Label(
                self, text=f"{label}:", font=("Menlo", 11),
                fg=MUTED, bg="#111111",
            ).grid(row=row, column=0, sticky="w", padx=15, pady=(10, 0))
            var = tk.StringVar(value=default)
            tk.Entry(
                self, textvariable=var,
                bg="#000000", fg="#ffffff", insertbackground="#ffffff",
                font=("Menlo", 11), borderwidth=1, relief=tk.FLAT,
                highlightthickness=1, highlightcolor="#333333", highlightbackground="#333333",
            ).grid(row=row, column=1, sticky="ew", padx=15, pady=(10, 0))
            setattr(self, f"_{key}_var", var)
            row += 1

        self._feedback = tk.Label(
            self, text="", font=("Menlo", 11),
            fg="#00cc66", bg="#111111",
        )
        self._feedback.grid(row=row, column=0, columnspan=2, pady=(10, 0))
        row += 1

        btn_frame = tk.Frame(self, bg="#111111")
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=15, pady=(15, 15))

        close_btn = tk.Label(
            btn_frame, text="  Close  ", bg="#222222", fg="#ffffff",
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        close_btn.pack(side=tk.RIGHT, padx=(5, 0))
        close_btn.bind("<Button-1>", lambda e: self.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#333333"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#222222"))

        add_btn = tk.Label(
            btn_frame, text="  Add  ", bg="#222222", fg="#ffffff",
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        add_btn.pack(side=tk.RIGHT)
        add_btn.bind("<Button-1>", lambda e: self._save())
        add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#333333"))
        add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#222222"))

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _on_type_select(self, event):
        idx = self._type_list.curselection()
        if idx and idx[0] < len(self._type_names):
            name = self._type_names[idx[0]]
            self._sel_type = name
            self._hascat_mode_var.set(self._type_modes.get(name, ""))
            example = self._type_examples.get(name, "")
            if example:
                show = example if len(example) < 80 else example[:80] + "..."
                self._example_label.config(text=f"  Example: {show}")
            else:
                self._example_label.config(text="")

    def _save(self):
        if not self._sel_type:
            return
        credential_db.save_hash_entry(
            self._sel_type,
            self._hash_var.get().strip(),
            self._salt_var.get().strip(),
            self._peper_var.get().strip(),
            self._hascat_mode_var.get().strip(),
            self._origin_obteined_var.get().strip(),
        )
        self._feedback.config(text="Done.")
        self.after(800, self.destroy)
