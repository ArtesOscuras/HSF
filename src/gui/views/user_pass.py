import tkinter as tk
from .base import BaseView
from src.machines import credential_db

BRIGHT = "#ffffff"
INFO = "#5ba3ec"


class UserPassView(BaseView):
    name = "user-pass"
    description = "Users and passwords"

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
            header, text="Users & Passwords",
            font=("Menlo", 22, "bold"), fg="#ffffff", bg="#000000",
        )
        self._title_label.pack(anchor="center")
        self._title_label.bind("<Button-1>", lambda e: self.master.activate_view("credentials"))
        self._title_label.bind("<Enter>", lambda e: self._title_label.config(font=("Menlo", 22, "bold", "underline")))
        self._title_label.bind("<Leave>", lambda e: self._title_label.config(font=("Menlo", 22, "bold")))

        content = tk.Frame(self, bg="#000000")
        content.grid(row=1, column=0, sticky="nsew", padx=(300, 300))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=0)
        content.rowconfigure(1, weight=0)
        content.rowconfigure(2, weight=1)

        tk.Label(
            content, text="Users",
            font=("Menlo", 14, "bold"), fg=BRIGHT, bg="#000000",
        ).grid(row=0, column=0, pady=(10, 5))

        tk.Label(
            content, text="Passwords",
            font=("Menlo", 14, "bold"), fg=BRIGHT, bg="#000000",
        ).grid(row=0, column=1, pady=(10, 5))

        self._users_text = self._build_editor(content, 1, 0)
        self._pwds_text = self._build_editor(content, 1, 1)

        self._last_users = None
        self._last_pwds = None
        self._loaded = False
        self._poll_id = None

        btn_frame2 = tk.Frame(self, bg="#000000")
        btn_frame2.grid(row=2, column=0, pady=(10, 15))

        gen_btn = tk.Label(
            btn_frame2,
            text="  Generate credentials  ",
            bg="#222222", fg=BRIGHT,
            font=("Menlo", 12),
            relief=tk.RAISED, bd=1,
            padx=15, pady=8,
        )
        gen_btn.pack(side=tk.LEFT, padx=(0, 10))

        back_btn = tk.Label(
            btn_frame2, text="  \u2190 Back  ", bg="#222222", fg=BRIGHT,
            font=("Menlo", 12), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        back_btn.pack(side=tk.LEFT)

        gen_btn.bind("<Button-1>", lambda e: self._open_generator())
        gen_btn.bind("<Enter>", lambda e: gen_btn.config(bg="#333333"))
        gen_btn.bind("<Leave>", lambda e: gen_btn.config(bg="#222222"))
        back_btn.bind("<Button-1>", lambda e: self.master.activate_view("credentials"))
        back_btn.bind("<Enter>", lambda e: back_btn.config(bg="#333333"))
        back_btn.bind("<Leave>", lambda e: back_btn.config(bg="#222222"))

    def _build_editor(self, parent, row, col):
        text_frame = tk.Frame(parent, bg="#000000")
        text_frame.grid(row=row, column=col, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        text = tk.Text(
            text_frame, bg="#111111", fg=BRIGHT,
            font=("Menlo", 13), borderwidth=1,
            relief=tk.FLAT, pady=5, cursor="xterm",
            wrap=tk.NONE, height=12,
            highlightthickness=1,
            highlightcolor="#333333", highlightbackground="#333333",
            insertbackground=BRIGHT,
        )
        text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)

        return text

    def on_activate(self):
        self._loaded = False
        self.after(100, self._poll)

    def on_deactivate(self):
        self._sync_all()
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _poll(self):
        if not self._loaded:
            self._load_from_db()
            self._loaded = True
        else:
            self._sync_all()
        self._poll_id = self.after(2000, self._poll)

    def _load_from_db(self):
        users = credential_db.load_users()
        pwds = credential_db.load_passwords()

        self._users_text.delete("1.0", tk.END)
        for u in users:
            self._users_text.insert(tk.END, f"{u}\n")

        self._pwds_text.delete("1.0", tk.END)
        for p in pwds:
            self._pwds_text.insert(tk.END, f"{p}\n")

        self._last_users = users
        self._last_pwds = pwds

    def _sync_all(self):
        self._sync_text(self._users_text, self._last_users,
                        credential_db.delete_user, credential_db.save_user)
        self._sync_text(self._pwds_text, self._last_pwds,
                        credential_db.delete_password, credential_db.save_password)

    def _sync_text(self, text_widget, last_items, delete_fn, save_fn):
        content = text_widget.get("1.0", "end-1c")
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        if lines == (last_items or []):
            return

        for old in (last_items or []):
            delete_fn(old)
        for item in lines:
            save_fn(item)

        if text_widget is self._users_text:
            self._last_users = lines
        else:
            self._last_pwds = lines

    def _open_generator(self):
        dialog = _CredentialGenerator(self)
        if dialog.result:
            credential_db.save_credential(
                dialog.result["user"],
                dialog.result["password"],
                dialog.result.get("domain", ""),
                dialog.result.get("hash_nt", ""),
            )
            if self._on_cred_created:
                self._on_cred_created(dialog.result["user"], dialog.result["password"])


class _CredentialGenerator(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None

        self.title("Generate Credentials")
        self.geometry("600x500")
        self.configure(bg="#111111")

        self.transient(parent)
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)
        self.rowconfigure(3, weight=0)
        self.rowconfigure(4, weight=0)
        self.rowconfigure(5, weight=0)

        tk.Label(
            self, text="Users", font=("Menlo", 14, "bold"),
            fg=INFO, bg="#111111",
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        tk.Label(
            self, text="Passwords", font=("Menlo", 14, "bold"),
            fg=INFO, bg="#111111",
        ).grid(row=0, column=1, sticky="w", padx=15, pady=(15, 5))

        self._user_listbox = self._build_listbox(self, 1, 0)
        self._pwd_listbox = self._build_listbox(self, 1, 1)

        users = credential_db.load_users()
        pwds = credential_db.load_passwords()
        for u in users:
            self._user_listbox.insert(tk.END, f"  {u}")
        for p in pwds:
            self._pwd_listbox.insert(tk.END, f"  {p}")
        if users:
            self._user_listbox.selection_set(0)

        self._sel_user = users[0] if users else None
        self._sel_pwd = None

        self._user_listbox.bind("<<ListboxSelect>>", self._on_user_select)
        self._pwd_listbox.bind("<<ListboxSelect>>", self._on_pwd_select)

        self.bind("<Button-1>", self._on_dialog_click)

        domain_frame = tk.Frame(self, bg="#111111")
        domain_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(15, 0))
        tk.Label(
            domain_frame, text="Domain", font=("Menlo", 11, "bold"),
            fg=INFO, bg="#111111",
        ).pack(anchor="w")
        self._domain_var = tk.StringVar()
        tk.Entry(
            domain_frame, textvariable=self._domain_var,
            bg="#000000", fg="#ffffff", insertbackground="#ffffff",
            font=("Menlo", 11), borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333", highlightbackground="#333333",
        ).pack(fill=tk.X)

        hash_frame = tk.Frame(self, bg="#111111")
        hash_frame.grid(row=2, column=1, sticky="ew", padx=15, pady=(15, 0))
        tk.Label(
            hash_frame, text="Hash NT", font=("Menlo", 11, "bold"),
            fg=INFO, bg="#111111",
        ).pack(anchor="w")
        self._hash_var = tk.StringVar()
        tk.Entry(
            hash_frame, textvariable=self._hash_var,
            bg="#000000", fg="#ffffff", insertbackground="#ffffff",
            font=("Menlo", 11), borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333", highlightbackground="#333333",
        ).pack(fill=tk.X)

        self._feedback_label = tk.Label(
            self, text="", font=("Menlo", 11),
            fg="#00cc66", bg="#111111",
        )
        self._feedback_label.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        btn_frame = tk.Frame(self, bg="#111111")
        btn_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=15, pady=(15, 15))

        cancel_btn = tk.Label(
            btn_frame, text="  Close  ", bg="#222222", fg="#ffffff",
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
        cancel_btn.bind("<Button-1>", lambda e: self.destroy())
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg="#333333"))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg="#222222"))

        add_btn = tk.Label(
            btn_frame, text="  Add  ", bg="#222222", fg="#ffffff",
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        add_btn.pack(side=tk.RIGHT)
        add_btn.bind("<Button-1>", lambda e: self._select())
        add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#333333"))
        add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#222222"))

        self._user_listbox.bind("<Return>", lambda e: self._select())
        self._pwd_listbox.bind("<Return>", lambda e: self._select())

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    def _build_listbox(self, parent, row, col):
        frame = tk.Frame(parent, bg="#000000")
        frame.grid(row=row, column=col, sticky="nsew", padx=15, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        lb = tk.Listbox(
            frame, bg="#000000", fg="#ffffff",
            selectbackground="#333333", selectforeground="#ffffff",
            font=("Menlo", 12), borderwidth=0, highlightthickness=0,
            activestyle="none", exportselection=False,
        )
        lb.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=lb.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        lb.configure(yscrollcommand=scrollbar.set)

        return lb

    def _on_user_select(self, event):
        idx = self._user_listbox.curselection()
        if idx:
            self._sel_user = self._user_listbox.get(idx[0]).strip()

    def _on_pwd_select(self, event):
        idx = self._pwd_listbox.curselection()
        if idx:
            self._sel_pwd = self._pwd_listbox.get(idx[0]).strip()

    def _on_dialog_click(self, event):
        w = event.widget
        if w != self._pwd_listbox:
            self._pwd_listbox.selection_clear(0, tk.END)
            self._sel_pwd = None

    def _select(self):
        if not self._sel_user:
            return

        pwd = self._sel_pwd or ""
        hnt = self._hash_var.get().strip()
        credential_db.save_credential(
            self._sel_user,
            pwd,
            self._domain_var.get().strip(),
            hnt,
            "Generated by user" if pwd else "",
            "Generated by user" if hnt else "",
        )

        self.result = {
            "user": self._sel_user,
            "password": pwd,
            "domain": self._domain_var.get().strip(),
            "hash_nt": hnt,
        }

        self._feedback_label.config(text="Done.")
        self.after(1500, lambda: self._feedback_label.config(text=""))
