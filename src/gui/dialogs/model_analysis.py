import os
import threading
import tkinter as tk
from tkinter import ttk
from src.gui import fonts
from src.hsf_paths import evidence_dir as _evidence_dir

BG = "#111111"
BG_WIDGET = "#000000"
FG = "#ffffff"
FG_DIM = "#888888"
SUCCESS = "#00cc66"
INFO = "#5ba3ec"


class _ModelAnalysisDialog(tk.Toplevel):
    def __init__(self, parent, ev_name):
        super().__init__(parent)
        self._ev_name = ev_name
        self.title(f"Model Analysis — {ev_name}")
        sh = self.winfo_screenheight()
        w = min(1000, self.winfo_screenwidth() - 40)
        h = min(740, sh - 60)
        x = (self.winfo_screenwidth() - w) // 2
        y = max(0, (sh - h) // 2 - 20)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(700, 500)
        self.configure(bg=BG)
        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=0)
        self.rowconfigure(3, weight=1)
        self.rowconfigure(4, weight=0)
        self.rowconfigure(5, weight=0)
        self.rowconfigure(6, weight=0)
        self.rowconfigure(7, weight=0)
        self.rowconfigure(8, weight=0)

        self._chat_messages = []
        self._chat_history = []

        import src.llm.config as _cfg
        self._config = _cfg.load()
        prompt_default = self._config.get("prompts", {}).get(
            "evidence_analysis", "")

        tk.Label(
            self, text="System Prompt",
            font=fonts.view_font_bold(11), fg=FG, bg=BG,
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 3))

        self._prompt_text = tk.Text(
            self, bg=BG_WIDGET, fg=FG, insertbackground=FG,
            font=fonts.view_font(10), borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333",
            highlightbackground="#333333", height=6, wrap=tk.WORD,
        )
        self._prompt_text.insert("1.0", prompt_default)
        self._prompt_text.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))

        tk.Label(
            self, text="Analysis Output",
            font=fonts.view_font_bold(11), fg=FG, bg=BG,
        ).grid(row=2, column=0, sticky="w", padx=15, pady=(0, 3))

        output_frame = tk.Frame(self, bg=BG_WIDGET)
        output_frame.grid(row=3, column=0, sticky="nsew", padx=15, pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self._output_text = tk.Text(
            output_frame, bg=BG_WIDGET, fg=FG, insertbackground=FG,
            font=fonts.view_font(10), borderwidth=0, highlightthickness=0,
            state=tk.DISABLED, wrap=tk.WORD, pady=5, padx=8,
        )
        self._output_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(output_frame, orient=tk.VERTICAL,
                                 command=self._output_text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a",
                            activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0,
                            elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._output_text.configure(yscrollcommand=scrollbar.set)

        self._output_text.tag_configure("success", foreground=SUCCESS)
        self._output_text.tag_configure("info", foreground=INFO)
        self._output_text.tag_configure("muted", foreground=FG_DIM)
        self._output_text.tag_configure("bold", font=fonts.view_font_bold(10))
        self._output_text.tag_configure("code", foreground="#ce9178")
        self._output_text.tag_configure("heading", foreground=INFO,
                                         font=fonts.view_font_bold(11))
        self._output_text.tag_configure("user", foreground=INFO)

        tk.Label(
            self, text="Chat (ask follow-up questions):",
            font=fonts.view_font_bold(11), fg=FG, bg=BG,
        ).grid(row=4, column=0, sticky="w", padx=15, pady=(5, 3))

        chat_frame = tk.Frame(self, bg=BG)
        chat_frame.grid(row=5, column=0, sticky="ew", padx=15, pady=(0, 5))
        chat_frame.columnconfigure(0, weight=1)

        self._chat_entry = tk.Text(
            chat_frame, bg=BG_WIDGET, fg=FG, insertbackground=FG,
            font=fonts.view_font(10), borderwidth=1, relief=tk.FLAT,
            highlightthickness=1, highlightcolor="#333333",
            highlightbackground="#333333", height=3, wrap=tk.WORD,
        )
        self._chat_entry.grid(row=0, column=0, sticky="ew")
        self._chat_entry.bind("<Return>", self._on_chat_return)

        send_btn = tk.Label(
            chat_frame, text=" Send ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=12, pady=4,
        )
        send_btn.grid(row=0, column=1, padx=(5, 0))
        send_btn.bind("<Button-1>", lambda e: self._send_chat())
        send_btn.bind("<Enter>", lambda e: send_btn.config(bg="#333333"))
        send_btn.bind("<Leave>", lambda e: send_btn.config(bg="#222222"))

        self._progress_var = tk.IntVar(value=0)
        self._progress_bar = ttk.Progressbar(
            self, variable=self._progress_var, maximum=100,
        )
        self._progress_bar.grid(row=6, column=0, sticky="ew", padx=15, pady=(0, 3))

        self._progress_label = tk.Label(
            self, text="Ready", font=fonts.view_font(9),
            fg=FG_DIM, bg=BG, anchor="w",
        )
        self._progress_label.grid(row=7, column=0, sticky="ew", padx=15)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.grid(row=8, column=0, sticky="ew", padx=15, pady=(8, 15))

        close_btn = tk.Label(
            btn_frame, text="  Close  ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        close_btn.pack(side=tk.RIGHT, padx=(5, 0))
        close_btn.bind("<Button-1>", lambda e: self.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#333333"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#222222"))

        analyze_btn = tk.Label(
            btn_frame, text="  Analyze  ", bg="#222222", fg=FG,
            font=fonts.view_font(10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        analyze_btn.pack(side=tk.RIGHT)
        analyze_btn.bind("<Button-1>", lambda e: self._start_analysis())
        analyze_btn.bind("<Enter>", lambda e: analyze_btn.config(bg="#333333"))
        analyze_btn.bind("<Leave>", lambda e: analyze_btn.config(bg="#222222"))

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _log(self, text, tag=None):
        def _insert():
            self._output_text.configure(state=tk.NORMAL)
            if tag:
                self._output_text.insert(tk.END, text, tag)
            else:
                self._render_md_line(text)
            self._output_text.see(tk.END)
            self._output_text.configure(state=tk.DISABLED)
        self.after(0, _insert)

    def _render_md_line(self, line):
        import re
        stripped = line.rstrip()
        if not stripped:
            self._output_text.insert(tk.END, "\n")
            return
        if re.match(r"^#{1,3}\s", stripped):
            self._output_text.insert(tk.END, stripped + "\n", "heading")
            return
        pos = 0
        for m in re.finditer(
                r"(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)|(```)", stripped):
            if m.start() > pos:
                self._output_text.insert(tk.END, stripped[pos:m.start()])
            if m.group(2):
                self._output_text.insert(tk.END, m.group(2), "bold")
            elif m.group(4):
                self._output_text.insert(tk.END, m.group(4), "info")
            elif m.group(6):
                self._output_text.insert(tk.END, m.group(6), "code")
            elif m.group(7):
                self._output_text.insert(tk.END, m.group(7), "code")
            pos = m.end()
        if pos < len(stripped):
            self._output_text.insert(tk.END, stripped[pos:])
        self._output_text.insert(tk.END, "\n")

    def _on_chat_return(self, event):
        if event.state & 0x1:
            return
        self._send_chat()
        return "break"

    def _start_analysis(self):
        threading.Thread(target=self._run_analysis, daemon=True).start()

    def _send_chat(self):
        text = self._chat_entry.get("1.0", "end-1c").strip()
        if not text:
            return
        self._chat_entry.delete("1.0", tk.END)
        if not self._chat_messages:
            return
        self._log(f"\n> {text}\n", "info")
        self._chat_messages.append({"role": "user", "content": text})
        threading.Thread(target=self._run_chat, daemon=True).start()

    def _run_chat(self):
        try:
            from src.llm import LLMClient
            client = LLMClient()
            stream = client.chat_stream(self._chat_messages)
            full = ""
            buf = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    ctext = chunk.choices[0].delta.content
                    full += ctext
                    buf += ctext
                    if "\n" in buf:
                        lines = buf.split("\n")
                        for line in lines[:-1]:
                            self._log(line.rstrip() + "\n")
                        buf = lines[-1]
            if buf.strip():
                self._log(buf.rstrip() + "\n")
            self._chat_messages.append(
                {"role": "assistant", "content": full})
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: self._log(f"\nError: {msg}\n", "muted"))

    def _run_analysis(self):
        self.after(0, lambda: self._progress_label.config(
            text="Collecting evidence files..."))
        self.after(0, lambda: self._progress_var.set(10))

        base = str(_evidence_dir())
        ev_path = os.path.join(base, self._ev_name)
        if not os.path.isdir(ev_path):
            self._log("Evidence directory not found.\n", "muted")
            return

        files = []
        for root, _dirs, fnames in os.walk(ev_path):
            for fname in fnames:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue
                rel = os.path.relpath(fpath, ev_path)
                truncated = content[:20000]
                if len(content) > 20000:
                    truncated += "\n... (truncated)"
                files.append((rel, truncated))

        self.after(0, lambda: self._progress_label.config(
            text=f"Found {len(files)} files. Sending to model..."))
        self.after(0, lambda: self._progress_var.set(30))

        prompt = self._prompt_text.get("1.0", "end-1c").strip()

        context = f"Evidence directory: {self._ev_name}\n\nFiles:\n\n"
        for rel, content in files:
            context += f"=== {rel} ===\n{content}\n\n"

        system = prompt
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": context},
        ]
        self._chat_messages = list(messages)

        self.after(0, lambda: self._progress_var.set(50))
        self.after(0, lambda: self._progress_label.config(
            text="Waiting for model response..."))
        self._log("\n", "info")

        try:
            from src.llm import LLMClient
            client = LLMClient()
            stream = client.chat_stream(messages)
            full = ""
            buf = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full += text
                    buf += text
                    if "\n" in buf:
                        lines = buf.split("\n")
                        for line in lines[:-1]:
                            self._log(line.rstrip() + "\n")
                        buf = lines[-1]
            if buf.strip():
                self._log(buf.rstrip() + "\n")
            self._chat_messages.append(
                {"role": "assistant", "content": full})
            self.after(0, lambda: self._progress_var.set(100))
            self.after(0, lambda: self._progress_label.config(
                text="Analysis complete."))
            self._log("\n--- Analysis complete ---\n", "info")
        except Exception as e:
            msg = str(e)
            self.after(0, lambda m=msg: self._progress_label.config(
                text=f"Error: {m}"))
            self.after(0, lambda m=msg: self._log(f"\nError: {m}\n", "muted"))
