from src.gui import fonts
import os
import time
import tkinter as tk
from datetime import datetime
from src.machines import credential_db
from src.hsf_paths import logs_dir
from .base import BaseView
from .nav import build as build_nav

_DBG_FILE = os.path.join(logs_dir(), "debugging_logs")


def _dbg(msg):
    try:
        os.makedirs(os.path.dirname(_DBG_FILE), exist_ok=True)
        with open(_DBG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except (PermissionError, OSError):
        pass


MUTED = "#888888"
BRIGHT = "#ffffff"


class UsersView(BaseView):
    name = "users"
    description = "Manage users"

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        nav_frame = tk.Frame(header, bg="#000000")
        nav_frame.pack(pady=(0, 10))

        build_nav(header, "users", self.master)

        self._title_label = tk.Label(
            header, text="Users",
            font=fonts.view_font_bold(22), fg=BRIGHT, bg="#000000",
        )
        self._title_label.pack(anchor="center")
        self._title_label.bind("<Button-1>",
                               lambda e: self.master.activate_view("inventory"))
        self._title_label.bind("<Enter>",
                               lambda e: self._title_label.config(
                                   font=fonts.view_font_bold_under(22)))
        self._title_label.bind("<Leave>",
                               lambda e: self._title_label.config(
                                   font=fonts.view_font_bold(22)))

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame, bg="#000000", fg=BRIGHT,
            font=fonts.view_font(14), borderwidth=0, highlightthickness=0,
            pady=10, state=tk.DISABLED, cursor="",
            wrap=tk.NONE, spacing1=2, spacing3=2,
            padx=30,
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("bright", foreground=BRIGHT)

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL,
                                 command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a",
                            activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0,
                            elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        btn_frame = tk.Frame(self, bg="#000000")
        btn_frame.grid(row=2, column=0, pady=(15, 15))

        back_btn = tk.Label(
            btn_frame, text="  \u2190 Back  ", bg="#222222", fg=BRIGHT,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        back_btn.pack(side=tk.RIGHT, padx=(10, 0))
        back_btn.bind("<Button-1>",
                      lambda e: self.master.activate_view("inventory"))
        back_btn.bind("<Enter>", lambda e: back_btn.config(bg="#333333"))
        back_btn.bind("<Leave>", lambda e: back_btn.config(bg="#222222"))

        add_btn = tk.Label(
            btn_frame, text="  Add user  ", bg="#222222", fg=BRIGHT,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        add_btn.pack(side=tk.LEFT)
        add_btn.bind("<Button-1>", lambda e: self._open_add_dialog())
        add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#333333"))
        add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#222222"))

        self._last = None
        self._poll_id = None

    def on_activate(self):
        _dbg(f"[users] on_activate")
        self._last = None
        self.after(10, self._poll)

    def on_deactivate(self):
        _dbg(f"[users] on_deactivate")
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _poll(self):
        t0 = time.perf_counter()
        items = credential_db.load_users()
        _dbg(f"[users] _poll load_users took {time.perf_counter() - t0:.3f}s ({len(items)} items)")
        current = "|".join(items)
        if current == self._last:
            self._poll_id = self.after(2000, self._poll)
            return
        self._last = current

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        if not items:
            self.text.insert(tk.END, "\n\n", "bright")
            self.text.insert(tk.END, "    No users stored yet.\n", "muted")
        else:
            for item in items:
                self.text.insert(tk.END, f"    {item}\n", "bright")

        self.text.configure(state=tk.DISABLED)
        self._poll_id = self.after(2000, self._poll)

    def _open_add_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add User")
        dialog.geometry("400x160")
        dialog.configure(bg="#111111")
        dialog.transient(self)
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(
            dialog, text="Username:", font=fonts.view_font(11),
            fg=BRIGHT, bg="#111111",
        ).pack(pady=(15, 5))

        var = tk.StringVar()
        entry = tk.Entry(
            dialog, textvariable=var, bg="#000000", fg=BRIGHT,
            insertbackground=BRIGHT, font=fonts.view_font(12),
            borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333",
            highlightbackground="#333333",
        )
        entry.pack(padx=20, fill=tk.X)
        entry.focus()

        def _save():
            name = var.get().strip()
            if name:
                credential_db.save_user(name)
            dialog.destroy()

        entry.bind("<Return>", lambda e: _save())

        btn_frame = tk.Frame(dialog, bg="#111111")
        btn_frame.pack(pady=(10, 0))

        add_btn = tk.Label(
            btn_frame, text="  Add  ", bg="#222222", fg=BRIGHT,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        add_btn.pack(side=tk.LEFT, padx=(0, 5))
        add_btn.bind("<Button-1>", lambda e: _save())
        add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#333333"))
        add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#222222"))
