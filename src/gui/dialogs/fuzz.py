import os
import tkinter as tk
from tkinter import ttk

from src.fuzz import FuzzEngine
from src.machines import store
from src.machines import domain_db

BG = "#111111"
BG_WIDGET = "#000000"
FG = "#ffffff"
FG_DIM = "#888888"
SEL_BG = "#333333"
SUCCESS = "#00cc66"
ERR_COLOR = "#f44747"
INFO_COLOR = "#5ba3ec"


class FuzzDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._engine = None

        self.title("Fuzz")
        self.geometry("800x700")
        self.configure(bg=BG)

        self.transient(parent)
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)
        self.rowconfigure(4, weight=0)
        self.rowconfigure(5, weight=0)
        self.rowconfigure(6, weight=1)
        self.rowconfigure(7, weight=0)

        tk.Label(
            self, text="Fuzz Configuration", font=("Menlo", 16, "bold"),
            fg=FG, bg=BG,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(15, 10))

        self._build_target_section()
        self._build_wordlist_section()
        self._build_method_section()
        self._build_progress_section()
        self._build_output_section()
        self._build_buttons()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_target_section(self):
        tk.Label(
            self, text="Target", font=("Menlo", 11, "bold"),
            fg=FG, bg=BG,
        ).grid(row=1, column=0, sticky="w", padx=15, pady=(0, 5))

        mode_frame = tk.Frame(self, bg=BG)
        mode_frame.grid(row=1, column=1, sticky="w", padx=15, pady=(0, 5))

        self._target_mode = tk.StringVar(value="machine")

        machine_radio = tk.Radiobutton(
            mode_frame, text="  Machine  ", variable=self._target_mode, value="machine",
            bg=BG, fg=FG, selectcolor=BG, font=("Menlo", 10),
            activebackground=BG, activeforeground=FG,
            indicatoron=False, relief=tk.FLAT,
            command=self._switch_target_mode,
        )
        machine_radio.pack(side=tk.LEFT, padx=(0, 5))

        domain_radio = tk.Radiobutton(
            mode_frame, text="  Domain  ", variable=self._target_mode, value="domain",
            bg=BG, fg=FG, selectcolor=BG, font=("Menlo", 10),
            activebackground=BG, activeforeground=FG,
            indicatoron=False, relief=tk.FLAT,
            command=self._switch_target_mode,
        )
        domain_radio.pack(side=tk.LEFT)

        frame = tk.Frame(self, bg=BG_WIDGET)
        frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=15, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._target_listbox = tk.Listbox(
            frame, bg=BG_WIDGET, fg=FG,
            selectbackground=SEL_BG, selectforeground=FG,
            font=("Menlo", 11), borderwidth=0, highlightthickness=0,
            activestyle="none", exportselection=False, height=5,
        )
        self._target_listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self._target_listbox.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._target_listbox.configure(yscrollcommand=scrollbar.set)

        self._populate_targets()

    def _switch_target_mode(self):
        self._populate_targets()

    def _populate_targets(self):
        self._target_listbox.delete(0, tk.END)
        self._target_keys = []

        if self._target_mode.get() == "machine":
            machines = store.get_all_sorted()
            for m in machines:
                if m.ip in ("127.0.0.1", "::1") or m.ip.startswith("127."):
                    continue
                label = f"{m.ip:<18}{m.hostname or ''}".rstrip()
                self._target_listbox.insert(tk.END, f"  {label}")
                self._target_keys.append(("machine", m.ip, m.hostname, m.ip))
        else:
            domains = domain_db.list_all()
            domains.sort()
            for d in domains:
                self._target_listbox.insert(tk.END, f"  {d}")
                self._target_keys.append(("domain", d, d, None))

        if self._target_keys:
            self._target_listbox.selection_set(0)

    def _build_wordlist_section(self):
        tk.Label(
            self, text="Wordlist", font=("Menlo", 11, "bold"),
            fg=FG, bg=BG,
        ).grid(row=3, column=0, sticky="nw", padx=15, pady=(5, 5))

        frame = tk.Frame(self, bg=BG_WIDGET)
        frame.grid(row=3, column=1, sticky="nsew", padx=15, pady=(5, 5))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._wordlist_listbox = tk.Listbox(
            frame, bg=BG_WIDGET, fg=FG,
            selectbackground=SEL_BG, selectforeground=FG,
            font=("Menlo", 11), borderwidth=0, highlightthickness=0,
            activestyle="none", exportselection=False, height=3,
        )
        self._wordlist_listbox.grid(row=0, column=0, sticky="nsew")

        self._wordlist_files = []
        lst_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "lst")
        lst_dir = os.path.abspath(lst_dir)
        if os.path.isdir(lst_dir):
            for fname in sorted(os.listdir(lst_dir)):
                if os.path.isfile(os.path.join(lst_dir, fname)):
                    self._wordlist_files.append(os.path.join(lst_dir, fname))
                    self._wordlist_listbox.insert(tk.END, f"  {fname}")
        if self._wordlist_files:
            self._wordlist_listbox.selection_set(0)

    def _build_method_section(self):
        tk.Label(
            self, text="Method", font=("Menlo", 11, "bold"),
            fg=FG, bg=BG,
        ).grid(row=4, column=0, sticky="nw", padx=15, pady=(5, 0))

        method_frame = tk.Frame(self, bg=BG)
        method_frame.grid(row=4, column=1, sticky="w", padx=15, pady=(5, 0))

        self._method_var = tk.StringVar(value="directory")

        methods = [
            ("  Directory  ", "directory"),
            ("  Vhost subdomain  ", "vhost"),
            ("  DNS subdomain  ", "dns"),
        ]

        for text, value in methods:
            btn = tk.Radiobutton(
                method_frame, text=text, variable=self._method_var, value=value,
                bg=BG, fg=FG, selectcolor=BG, font=("Menlo", 10),
                activebackground=BG, activeforeground=FG,
                indicatoron=False, relief=tk.FLAT,
            )
            btn.pack(side=tk.LEFT, padx=(0, 5))

        self._thread_var = tk.StringVar(value="20")
        tk.Label(
            method_frame, text=" Threads:", font=("Menlo", 10),
            fg=FG_DIM, bg=BG,
        ).pack(side=tk.LEFT, padx=(15, 5))
        thread_entry = tk.Entry(
            method_frame, textvariable=self._thread_var, width=4,
            bg=BG_WIDGET, fg=FG, insertbackground=FG,
            font=("Menlo", 10), borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333", highlightbackground="#333333",
        )
        thread_entry.pack(side=tk.LEFT)

    def _build_progress_section(self):
        frame = tk.Frame(self, bg=BG)
        frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=15, pady=(5, 2))

        self._progress_var = tk.IntVar(value=0)
        self._progress_bar = ttk.Progressbar(
            frame, variable=self._progress_var, maximum=100,
        )
        self._progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._progress_label = tk.Label(
            frame, text="  Ready", font=("Menlo", 9),
            fg=FG_DIM, bg=BG,
        )
        self._progress_label.pack(side=tk.LEFT, padx=(8, 0))

    def _build_output_section(self):
        tk.Label(
            self, text="Output", font=("Menlo", 11, "bold"),
            fg=FG, bg=BG,
        ).grid(row=6, column=0, sticky="nw", padx=15, pady=(10, 5))

        frame = tk.Frame(self, bg=BG_WIDGET)
        frame.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=15, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._output_text = tk.Text(
            frame, bg=BG_WIDGET, fg=FG_DIM, insertbackground=FG,
            font=("Menlo", 10), borderwidth=0, highlightthickness=0,
            state=tk.DISABLED, wrap=tk.WORD,
        )
        self._output_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self._output_text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._output_text.configure(yscrollcommand=scrollbar.set)

        self._output_text.tag_configure("success", foreground=SUCCESS)
        self._output_text.tag_configure("error", foreground=ERR_COLOR)
        self._output_text.tag_configure("info", foreground=INFO_COLOR)

    def _build_buttons(self):
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=15, pady=(10, 15))

        self._close_btn = tk.Label(
            btn_frame, text="  Close  ", bg="#222222", fg=FG,
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6, cursor="hand2",
        )
        self._close_btn.pack(side=tk.RIGHT, padx=(5, 0))
        self._close_btn.bind("<Button-1>", lambda e: self._on_close())
        self._close_btn.bind("<Enter>", lambda e: self._close_btn.config(bg="#333333"))
        self._close_btn.bind("<Leave>", lambda e: self._close_btn.config(bg="#222222"))

        self._stop_btn = tk.Label(
            btn_frame, text="  Stop  ", bg="#222222", fg=FG,
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6, cursor="hand2",
        )
        self._stop_btn.pack(side=tk.RIGHT, padx=(5, 0))
        self._stop_btn.bind("<Button-1>", lambda e: self._stop())
        self._stop_btn.bind("<Enter>", lambda e: self._stop_btn.config(bg="#333333"))
        self._stop_btn.bind("<Leave>", lambda e: self._stop_btn.config(bg="#222222"))

        self._start_btn = tk.Label(
            btn_frame, text="  Start  ", bg="#222222", fg=FG,
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6, cursor="hand2",
        )
        self._start_btn.pack(side=tk.RIGHT, padx=(5, 0))
        self._start_btn.bind("<Button-1>", lambda e: self._start())
        self._start_btn.bind("<Enter>", lambda e: self._start_btn.config(bg="#333333"))
        self._start_btn.bind("<Leave>", lambda e: self._start_btn.config(bg="#222222"))

        self._target_listbox.bind("<Return>", lambda e: self._start())
        self._wordlist_listbox.bind("<Return>", lambda e: self._start())

    def _selected_target(self):
        sel = self._target_listbox.curselection()
        if not sel:
            return None
        return self._target_keys[sel[0]]

    def _selected_wordlist(self):
        sel = self._wordlist_listbox.curselection()
        if not sel:
            return None
        return self._wordlist_files[sel[0]]

    def _write_output(self, text, color=None):
        self.after(0, lambda: self._do_write(text, color))

    def _do_write(self, text, color=None):
        if not self.winfo_exists():
            return
        self._output_text.configure(state=tk.NORMAL)
        is_at_bottom = self._output_text.yview()[1] >= 1.0
        if color:
            self._output_text.insert(tk.END, text, color)
        else:
            self._output_text.insert(tk.END, text)
        if is_at_bottom:
            self._output_text.see(tk.END)
        self._output_text.configure(state=tk.DISABLED)

    def _start(self):
        target = self._selected_target()
        wordlist = self._selected_wordlist()
        if not target or not wordlist:
            return

        target_type, target_val, target_label, target_ip = target
        method = self._method_var.get()
        wordlist_name = os.path.basename(wordlist)
        try:
            workers = int(self._thread_var.get())
        except ValueError:
            workers = 20

        self._write_output(f"\n[*] Starting fuzz: target={target_label} method={method} wordlist={wordlist_name} threads={workers}\n", "info")

        if method == "directory":
            fuzz_target = target_val if target_type == "machine" and target_ip else target_val
            self._engine = FuzzEngine(
                target=fuzz_target, wordlist_path=wordlist, method="directory",
                target_ip=None, on_result=self._write_output, workers=workers,
                on_progress=self._on_progress,
            )
        elif method == "vhost":
            ip = target_ip if target_type == "machine" and target_ip else target_val
            self._engine = FuzzEngine(
                target=target_val, wordlist_path=wordlist, method="vhost",
                target_ip=ip, on_result=self._write_output, workers=workers,
                on_progress=self._on_progress,
            )
        else:
            self._engine = FuzzEngine(
                target=target_val, wordlist_path=wordlist, method="dns",
                target_ip=None, on_result=self._write_output, workers=workers,
                on_progress=self._on_progress,
            )
        self._engine.start()

    def _stop(self):
        if self._engine:
            self._engine.stop()

    def _on_progress(self, done, total, found):
        self.after(0, lambda: self._progress_var.set(int(done * 100 / max(total, 1))))
        self.after(0, lambda: self._progress_label.config(
            text=f" {done}/{total}  found: {found}"
        ))

    def _on_close(self):
        self._stop()
        self.destroy()
