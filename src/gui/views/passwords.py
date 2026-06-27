import tkinter as tk
from src.gui import fonts
from src.machines import credential_db
from .base import BaseView
from .nav import build as build_nav

MUTED = "#888888"
BRIGHT = "#ffffff"


class PasswordsView(BaseView):
    name = "passwords"
    description = "Manage passwords"

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        nav_frame = tk.Frame(header, bg="#000000")
        nav_frame.pack(pady=(0, 10))

        build_nav(header, "passwords", self.master)

        self._title_label = tk.Label(
            header, text="Passwords",
            font=fonts.view_font_bold(22), fg=BRIGHT, bg="#000000",
        )
        self._title_label.pack(anchor="center")
        self._title_label.bind(
            "<Button-1>",
            lambda e: self.master.activate_view("inventory"))
        self._title_label.bind(
            "<Enter>",
            lambda e: self._title_label.config(
                font=fonts.view_font_bold_under(22)))
        self._title_label.bind(
            "<Leave>",
            lambda e: self._title_label.config(
                font=fonts.view_font_bold(22)))

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew",
                        padx=(300, 300), pady=(0, 10))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame, bg="#111111", fg=BRIGHT,
            font=fonts.view_font(13), borderwidth=1,
            relief=tk.FLAT, pady=10, padx=15,
            cursor="xterm", wrap=tk.NONE,
            highlightthickness=1,
            highlightcolor="#333333", highlightbackground="#333333",
            insertbackground=BRIGHT,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL,
                                 command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a",
                            activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0,
                            elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        btn_frame = tk.Frame(self, bg="#000000")
        btn_frame.grid(row=2, column=0, pady=(10, 15))

        back_btn = tk.Label(
            btn_frame, text="  \u2190 Back  ", bg="#222222", fg=BRIGHT,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        back_btn.pack(side=tk.LEFT)
        back_btn.bind("<Button-1>",
                      lambda e: self.master.activate_view("inventory"))
        back_btn.bind("<Enter>", lambda e: back_btn.config(bg="#333333"))
        back_btn.bind("<Leave>", lambda e: back_btn.config(bg="#222222"))

        self._last_items = None
        self._loaded = False
        self._poll_id = None

    def on_activate(self):
        self._loaded = False
        self.after(100, self._poll)

    def on_deactivate(self):
        self._sync()
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _poll(self):
        if not self._loaded:
            self._load_from_db()
            self._loaded = True
        else:
            self._sync()
        self._poll_id = self.after(2000, self._poll)

    def _load_from_db(self):
        items = credential_db.load_passwords()
        self.text.delete("1.0", tk.END)
        for p in items:
            self.text.insert(tk.END, f"{p}\n")
        self._last_items = items

    def _sync(self):
        content = self.text.get("1.0", "end-1c")
        lines = [l.strip() for l in content.split("\n") if l.strip()]

        db_items = credential_db.load_passwords()
        if set(lines) != set(db_items):
            self._load_from_db()
            return

        if lines == (self._last_items or []):
            return

        for old in (self._last_items or []):
            if old not in lines:
                credential_db.delete_password(old)
        for item in lines:
            if not self._last_items or item not in self._last_items:
                credential_db.save_password(item)

        self._last_items = lines
