import tkinter as tk
from tkinter import ttk
from src.gui import fonts
from src import llm

BG = "#111111"
BG_WIDGET = "#000000"
FG = "#ffffff"
FG_DIM = "#888888"
SEL_BG = "#333333"
SUCCESS = "#00cc66"
ERR = "#f44747"
INFO = "#5ba3ec"


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("HSF — Settings")
        sh = self.winfo_screenheight()
        h = min(680, sh - 60)
        w = 800
        x = (self.winfo_screenwidth() - w) // 2
        y = max(0, (sh - h) // 2 - 20)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(700, 560)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#222222",
                        foreground=FG_DIM, font=fonts.view_font(10),
                        padding=[14, 6])
        style.map("TNotebook.Tab", background=[("selected", BG)],
                  foreground=[("selected", FG)])

        self._nb = ttk.Notebook(self)
        self._nb.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        self._tab_models = tk.Frame(self._nb, bg=BG)
        self._nb.add(self._tab_models, text="  Models  ")
        self._build_models_tab(self._tab_models)

        self._tab_prompts = tk.Frame(self._nb, bg=BG)
        self._nb.add(self._tab_prompts, text="  Prompts  ")
        self._build_prompts_tab(self._tab_prompts)

        self._nb.select(0)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ─── Prompts Tab ─────────────────────────────────────────

    def _build_prompts_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=0)

        tk.Label(
            parent, text="System Prompts",
            font=fonts.view_font_bold(11), fg=FG, bg=BG,
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))

        prompts_frame = tk.Frame(parent, bg=BG_WIDGET)
        prompts_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 5))
        prompts_frame.columnconfigure(0, weight=1)
        prompts_frame.rowconfigure(0, weight=1)

        self._prompts_text = tk.Text(
            prompts_frame, bg=BG_WIDGET, fg=FG, insertbackground=FG,
            font=fonts.view_font(10), borderwidth=0, highlightthickness=0,
            wrap=tk.WORD, pady=8, padx=12,
        )
        self._prompts_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(prompts_frame, orient=tk.VERTICAL,
                                 command=self._prompts_text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a",
                            activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0,
                            elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._prompts_text.configure(yscrollcommand=scrollbar.set)

        self._prompts_text.tag_configure("section", foreground=INFO)
        self._prompts_text.tag_configure("muted", foreground=FG_DIM)

        self._refresh_prompts()

        btn_frame = tk.Frame(parent, bg=BG)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 10))

        save_btn = tk.Label(
            btn_frame, text="  Save  ", bg="#222222", fg=SUCCESS,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        save_btn.pack()
        save_btn.bind("<Button-1>", lambda e: self._prompts_save())
        save_btn.bind("<Enter>", lambda e: save_btn.config(bg="#333333"))
        save_btn.bind("<Leave>", lambda e: save_btn.config(bg="#222222"))

    def _refresh_prompts(self):
        prompts = self._config.get("prompts", {})
        self._prompts_text.delete("1.0", tk.END)
        for key, text in prompts.items():
            self._prompts_text.insert(tk.END, f"\u2500\u2500 {key} \u2500\u2500\n", "section")
            self._prompts_text.insert(tk.END, f"{text}\n\n")

    def _prompts_save(self):
        content = self._prompts_text.get("1.0", "end-1c")
        prompts = {}
        sections = content.split("\u2500\u2500 ")
        for sec in sections:
            if not sec.strip():
                continue
            parts = sec.split(" \u2500\u2500\n", 1)
            if len(parts) != 2:
                continue
            key = parts[0].strip()
            text = parts[1].strip()
            if key:
                prompts[key] = text
        self._config["prompts"] = prompts
        llm.config.save(self._config)
        self._refresh_prompts()

    # ─── Models Tab ──────────────────────────────────────────

    def _build_models_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=0)

        self._config = llm.config.load()

        tk.Label(
            parent, text="Models Configuration",
            font=fonts.view_font_bold(11), fg=FG, bg=BG,
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))

        list_frame = tk.Frame(parent, bg=BG_WIDGET)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 5))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self._prov_text = tk.Text(
            list_frame, bg=BG_WIDGET, fg=FG, insertbackground=FG,
            font=fonts.view_font(11), borderwidth=0, highlightthickness=0,
            state=tk.DISABLED, cursor="", wrap=tk.WORD, pady=8, padx=12,
        )
        self._prov_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self._prov_text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a",
                            activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0,
                            elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._prov_text.configure(yscrollcommand=scrollbar.set)

        self._prov_text.tag_configure("active", foreground=SUCCESS)
        self._prov_text.tag_configure("bright", foreground=FG)
        self._prov_text.tag_configure("muted", foreground=FG_DIM)
        self._prov_text.tag_configure("info", foreground=INFO)
        self._prov_text.tag_configure("error", foreground=ERR)

        btn_frame = tk.Frame(parent, bg=BG)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 10))

        close_btn = tk.Label(
            btn_frame, text="  Close  ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        close_btn.pack(side=tk.RIGHT, padx=(5, 0))
        close_btn.bind("<Button-1>", lambda e: self.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#333333"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#222222"))

        add_btn = tk.Label(
            btn_frame, text="  Add provider  ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        add_btn.pack(side=tk.RIGHT, padx=(5, 0))
        add_btn.bind("<Button-1>", lambda e: self._open_provider_dialog(is_new=True))
        add_btn.bind("<Enter>", lambda e: add_btn.config(bg="#333333"))
        add_btn.bind("<Leave>", lambda e: add_btn.config(bg="#222222"))

        edit_btn = tk.Label(
            btn_frame, text="  Edit / Set active  ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        edit_btn.pack(side=tk.RIGHT, padx=(5, 0))
        edit_btn.bind("<Button-1>", lambda e: self._open_provider_dialog())
        edit_btn.bind("<Enter>", lambda e: edit_btn.config(bg="#333333"))
        edit_btn.bind("<Leave>", lambda e: edit_btn.config(bg="#222222"))

        save_btn = tk.Label(
            btn_frame, text="  Save  ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        save_btn.pack(side=tk.RIGHT, padx=(5, 0))
        save_btn.bind("<Button-1>", lambda e: _main_save())
        save_btn.bind("<Enter>", lambda e: save_btn.config(bg="#333333"))
        save_btn.bind("<Leave>", lambda e: save_btn.config(bg="#222222"))

        self._prov_entries = []
        self._refresh_providers()

    def _refresh_providers(self):
        self._prov_text.configure(state=tk.NORMAL)
        self._prov_text.delete("1.0", tk.END)
        self._prov_entries = []

        providers = self._config.get("providers", {})
        active = self._config.get("active_provider", "")
        active_models = self._config.get("active_models", {})

        if not providers:
            self._prov_text.insert(tk.END, "\n  No providers configured.\n", "muted")
            self._prov_text.configure(state=tk.DISABLED)
            self._prov_view = providers
            return

        self._prov_view = providers

        for pid, p in providers.items():
            is_active = pid == active
            marker = "\u25cf" if is_active else "\u25cb"
            tag_marker = f"p_{pid}_marker"
            tag_name = f"p_{pid}_name"

            self._prov_text.tag_configure(tag_marker, foreground=SUCCESS if is_active else FG_DIM,
                                          underline=False)
            self._prov_text.tag_configure(tag_name, foreground=FG, underline=False)

            self._prov_text.insert(tk.END, f"  {marker}  ", (tag_marker,))
            self._prov_text.insert(tk.END, f"{pid}", (tag_name,))
            if is_active:
                self._prov_text.insert(tk.END, "  \u2190 active", "active")
            self._prov_text.insert(tk.END, "\n")

            url = p.get("base_url", "") or "(no URL set)"
            self._prov_text.insert(tk.END, f"      {url}\n", "muted")

            models = p.get("models", [])
            model_str = ", ".join(models) if models else "(no models)"
            am = active_models.get(pid, "")
            if is_active and am:
                model_str += f"  [active: {am}]"
            elif is_active and models:
                model_str += f"  [active: {models[0]}]"
            self._prov_text.insert(tk.END, f"      Models: {model_str}\n", "info")

            self._prov_text.insert(tk.END, "\n")
            self._prov_entries.append(pid)

            self._prov_text.tag_bind(tag_name, "<Enter>",
                                     lambda e, t=tag_name: self._prov_text.tag_configure(t, underline=True))
            self._prov_text.tag_bind(tag_name, "<Leave>",
                                     lambda e, t=tag_name: self._prov_text.tag_configure(t, underline=False))
            self._prov_text.tag_bind(tag_name, "<Button-1>",
                                     lambda e, p=pid: self._open_provider_dialog(preselected=p))

            self._prov_text.tag_bind(tag_marker, "<Enter>",
                                     lambda e, t=tag_marker: self._prov_text.tag_configure(t, underline=True))
            self._prov_text.tag_bind(tag_marker, "<Leave>",
                                     lambda e, t=tag_marker: self._prov_text.tag_configure(t, underline=False))
            self._prov_text.tag_bind(tag_marker, "<Button-1>",
                                     lambda e, p=pid: self._set_active(p))

        self._prov_text.configure(state=tk.DISABLED)

    def _set_active(self, pid):
        if pid not in self._config.get("providers", {}):
            return
        self._config["active_provider"] = pid
        llm.config.save(self._config)
        self._refresh_providers()

    # ─── Provider Edit Dialog ────────────────────────────────

    def _open_provider_dialog(self, is_new=False, preselected=None):
        dialog = tk.Toplevel(self)
        dialog.title("New Provider" if is_new else "Edit Provider")
        dialog.geometry("540x520")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()

        dialog.columnconfigure(0, weight=0)
        dialog.columnconfigure(1, weight=1)

        providers = self._config.get("providers", {})
        active = self._config.get("active_provider", "")
        active_models = self._config.get("active_models", {})

        row = 0

        if not is_new:
            tk.Label(
                dialog, text="Provider:", font=fonts.view_font(11),
                fg=FG_DIM, bg=BG,
            ).grid(row=row, column=0, sticky="w", padx=15, pady=(10, 3))
            pid_var = tk.StringVar(value=active)
            pids = list(providers.keys())
            combo = ttk.Combobox(
                dialog, textvariable=pid_var, values=pids,
                state="readonly", font=fonts.view_font(11),
            )
            combo.grid(row=row, column=1, sticky="ew", padx=15, pady=(10, 3))
            sel = preselected or active
            if pids:
                idx = pids.index(sel) if sel in pids else 0
                pid_var.set(pids[idx])
                combo.current(idx)
            row += 1
        else:
            tk.Label(
                dialog, text="ID:", font=fonts.view_font(11),
                fg=FG_DIM, bg=BG,
            ).grid(row=row, column=0, sticky="w", padx=15, pady=(10, 3))
            pid_var = tk.StringVar()
            tk.Entry(
                dialog, textvariable=pid_var, bg=BG_WIDGET, fg=FG,
                insertbackground=FG, font=fonts.view_font(11),
                borderwidth=1, relief=tk.FLAT,
                highlightthickness=1, highlightcolor="#333333",
                highlightbackground="#333333",
            ).grid(row=row, column=1, sticky="ew", padx=15, pady=(10, 3))
            row += 1

        tk.Label(
            dialog, text="Name:", font=fonts.view_font(11),
            fg=FG_DIM, bg=BG,
        ).grid(row=row, column=0, sticky="w", padx=15, pady=(5, 3))
        name_var = tk.StringVar()
        tk.Entry(
            dialog, textvariable=name_var, bg=BG_WIDGET, fg=FG,
            insertbackground=FG, font=fonts.view_font(11),
            borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333",
            highlightbackground="#333333",
        ).grid(row=row, column=1, sticky="ew", padx=15, pady=(5, 3))
        row += 1

        tk.Label(
            dialog, text="Base URL:", font=fonts.view_font(11),
            fg=FG_DIM, bg=BG,
        ).grid(row=row, column=0, sticky="w", padx=15, pady=(5, 3))
        url_var = tk.StringVar()
        tk.Entry(
            dialog, textvariable=url_var, bg=BG_WIDGET, fg=FG,
            insertbackground=FG, font=fonts.view_font(11),
            borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333",
            highlightbackground="#333333",
        ).grid(row=row, column=1, sticky="ew", padx=15, pady=(5, 3))
        row += 1

        tk.Label(
            dialog, text="API Key:", font=fonts.view_font(11),
            fg=FG_DIM, bg=BG,
        ).grid(row=row, column=0, sticky="w", padx=15, pady=(5, 3))
        key_var = tk.StringVar()
        tk.Entry(
            dialog, textvariable=key_var, show="*",
            bg=BG_WIDGET, fg=FG, insertbackground=FG,
            font=fonts.view_font(11), borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333",
            highlightbackground="#333333",
        ).grid(row=row, column=1, sticky="ew", padx=15, pady=(5, 3))
        row += 1

        tk.Label(
            dialog, text="Models:", font=fonts.view_font(11),
            fg=FG_DIM, bg=BG,
        ).grid(row=row, column=0, sticky="w", padx=15, pady=(5, 3))
        models_var = tk.StringVar()
        tk.Entry(
            dialog, textvariable=models_var, bg=BG_WIDGET, fg=FG,
            insertbackground=FG, font=fonts.view_font(11),
            borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333",
            highlightbackground="#333333",
        ).grid(row=row, column=1, sticky="ew", padx=15, pady=(5, 3))
        row += 1

        if not is_new:
            tk.Label(
                dialog, text="Active model:", font=fonts.view_font(11),
                fg=FG_DIM, bg=BG,
            ).grid(row=row, column=0, sticky="w", padx=15, pady=(5, 3))
            model_var = tk.StringVar(value=active_models.get(active, ""))
            tk.Entry(
                dialog, textvariable=model_var, bg=BG_WIDGET, fg=FG,
                insertbackground=FG, font=fonts.view_font(11),
                borderwidth=1, relief=tk.FLAT,
                highlightthickness=1, highlightcolor="#333333",
                highlightbackground="#333333",
            ).grid(row=row, column=1, sticky="ew", padx=15, pady=(5, 3))
            row += 1

        feedback = tk.Label(
            dialog, text="", font=fonts.view_font(9),
            fg=SUCCESS, bg=BG,
        )
        feedback.grid(row=row, column=0, columnspan=2, pady=(8, 0))
        row += 1

        btn_inner = tk.Frame(dialog, bg=BG)
        btn_inner.grid(row=row, column=0, columnspan=2, sticky="ew",
                       padx=15, pady=(10, 10))

        tk.Label(
            btn_inner, text="  Close  ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        ).pack(side=tk.RIGHT, padx=(5, 0))
        close_btn = btn_inner.winfo_children()[-1]
        close_btn.bind("<Button-1>", lambda e: dialog.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#333333"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#222222"))

        save_btn = tk.Label(
            btn_inner, text="  Save  ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        save_btn.pack(side=tk.RIGHT)
        save_btn.bind("<Enter>", lambda e: save_btn.config(bg="#333333"))
        save_btn.bind("<Leave>", lambda e: save_btn.config(bg="#222222"))

        if not is_new:
            del_btn = tk.Label(
                btn_inner, text="  Delete  ", bg="#222222", fg=ERR,
                font=fonts.view_font(10), relief=tk.RAISED, bd=1,
                padx=15, pady=6,
            )
            del_btn.pack(side=tk.RIGHT, padx=(5, 0))
            del_btn.bind("<Enter>", lambda e: del_btn.config(bg="#333333"))
            del_btn.bind("<Leave>", lambda e: del_btn.config(bg="#222222"))

            def _delete():
                pid = pid_var.get().strip()
                if pid not in providers:
                    return
                if len(providers) <= 1:
                    feedback.config(text="Cannot delete the last provider.")
                    dialog.after(1500, lambda: feedback.config(text=""))
                    return
                del providers[pid]
                if self._config["active_provider"] == pid:
                    remaining = list(providers.keys())
                    self._config["active_provider"] = remaining[0]
                    self._config["active_model"] = ""
                self._config["providers"] = providers
                llm.config.save(self._config)
                self._refresh_providers()
                feedback.config(text=f"Deleted '{pid}'.")
                dialog.after(800, dialog.destroy)

            del_btn.bind("<Button-1>", lambda e: _delete())

        def _load_provider():
            pid = pid_var.get().strip()
            if is_new:
                name_var.set("")
                url_var.set("")
                key_var.set("")
                models_var.set("")
                return
            p = providers.get(pid, {})
            name_var.set(p.get("name", pid))
            url_var.set(p.get("base_url", ""))
            key_var.set(p.get("api_key", ""))
            models_var.set(", ".join(p.get("models", [])))
            if not is_new:
                model_var.set(active_models.get(pid, ""))

        def _save():
            pid = pid_var.get().strip()
            if not pid:
                return
            if is_new and pid in providers:
                feedback.config(text="ID already exists.")
                dialog.after(1500, lambda: feedback.config(text=""))
                return
            models = [m.strip() for m in models_var.get().split(",")
                      if m.strip()]
            providers[pid] = {
                "name": name_var.get().strip() or pid,
                "base_url": url_var.get().strip(),
                "api_key": key_var.get().strip(),
                "models": models,
            }
            if not is_new:
                active_models[pid] = model_var.get().strip()
                self._config["active_models"] = active_models
            self._config["providers"] = providers
            if not is_new:
                self._config["active_provider"] = pid
            llm.config.save(self._config)
            self._refresh_providers()
            feedback.config(text="Saved.")
            dialog.after(800, dialog.destroy)

        if not is_new:
            combo.bind("<<ComboboxSelected>>", lambda e: _load_provider())
            _load_provider()

        save_btn.bind("<Button-1>", lambda e: _save())
