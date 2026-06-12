import tkinter as tk
from .base import BaseView
from src.machines import domain_db

MUTED = "#888888"
BRIGHT = "#ffffff"
INFO = "#5ba3ec"


class DomainDetailView(BaseView):
    name = "domain_detail"
    description = "Domain detail view"

    def __init__(self, parent, domain, **kwargs):
        self._domain = domain
        self._last_hash = None
        self._subdomain_rows = []
        self._machine_rows = []
        super().__init__(parent, **kwargs)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 10))

        self._title_label = tk.Label(
            header,
            text="",
            font=("Menlo", 22, "bold"),
            fg="#ffffff",
            bg="#000000",
            cursor="hand2",
        )
        self._title_label.pack(anchor="center")
        self._title_label.bind("<Button-1>", self._on_title_click)
        self._on_back_click = None

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew", padx=(220, 20), pady=(0, 20))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            bg="#000000",
            fg=BRIGHT,
            font=("Menlo", 13),
            borderwidth=0,
            highlightthickness=0,
            state=tk.DISABLED,
            wrap=tk.WORD,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("bright", foreground=BRIGHT)
        self.text.tag_configure("info", foreground=INFO)

        self._poll_id = None

    def on_activate(self):
        self.text.bind("<Button-1>", self._on_line_click)
        self.text.bind("<Motion>", self._on_mouse_move)
        self._poll()

    def on_deactivate(self):
        self.text.unbind("<Button-1>")
        self.text.unbind("<Motion>")
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _on_title_click(self, event):
        if self._on_back_click:
            self._on_back_click()

    def _on_line_click(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0])
        for row, sub in self._subdomain_rows:
            if line == row:
                if self._on_subdomain_click:
                    self._on_subdomain_click(sub)
                return "break"
        for row, ip in self._machine_rows:
            if line == row:
                if self._on_machine_click:
                    self._on_machine_click(ip)
                return "break"
        return "break"

    def _on_mouse_move(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0])
        cursor = ""
        for row, _ in self._subdomain_rows:
            if line == row:
                cursor = "hand2"
                break
        if not cursor:
            for row, _ in self._machine_rows:
                if line == row:
                    cursor = "hand2"
                    break
        self.text.configure(cursor=cursor)

    def _poll(self):
        self._refresh()
        self._poll_id = self.after(2000, self._poll)

    def _refresh(self):
        info = domain_db.load_domain_info(self._domain)
        machines = domain_db.load_domain_machines(self._domain)
        subdomains = domain_db.load_subdomains(self._domain)
        directories = domain_db.load_directories(self._domain)
        web = domain_db.load_web_services(self._domain)

        current_hash = hash((
            self._domain,
            tuple(info.items()) if info else None,
            tuple(tuple(m.items()) for m in machines),
            tuple(subdomains),
            tuple(directories),
            tuple(web),
        ))
        if current_hash == self._last_hash and self.text.index("end-1c") != "1.0":
            return
        self._last_hash = current_hash

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        self._title_label.config(text=f"Domain — {self._domain}")

        first = info.get("first_seen", "") if info else ""
        last = info.get("last_seen", "") if info else ""
        if first and "T" in first:
            first = first[:19].replace("T", " ")
        if last and "T" in last:
            last = last[:19].replace("T", " ")

        rows = [
            ("Domain", self._domain),
            ("First seen", first),
            ("Last seen", last),
        ]
        label_w = max(len(r[0]) for r in rows) + 2
        for label, value in rows:
            self.text.insert(tk.END, f"  {label + ':':<{label_w}} ", "muted")
            self.text.insert(tk.END, f"{value or '-'}\n", "bright")

        if subdomains:
            self._subdomain_rows = []
            self.text.insert(tk.END, f"\nSubdomains ({len(subdomains)}):\n", "info")
            sub_w = max(len(s[0]) for s in subdomains) + 2
            for sub, ts, method in subdomains:
                row_start = int(self.text.index("end-1c").split(".")[0])
                self.text.insert(tk.END, f"  {sub:<{sub_w}}", "bright")
                if method:
                    self.text.insert(tk.END, f" ({method})", "muted")
                t = ts.replace("T", " ") if "T" in ts else ts
                self.text.insert(tk.END, f"  {t}\n", "muted")
                self._subdomain_rows.append((row_start, sub))
        else:
            self._subdomain_rows = []
            parts = self._domain.split(".")
            if len(parts) > 2:
                parent = ".".join(parts[1:])
                if domain_db.exists(parent):
                    self.text.insert(tk.END, f"\nParent domain:\n", "info")
                    row_start = int(self.text.index("end-1c").split(".")[0])
                    self.text.insert(tk.END, f"  {parent}\n", "bright")
                    self._subdomain_rows.append((row_start, parent))
            else:
                self.text.insert(tk.END, "\nSubdomains: (none found yet)\n", "muted")

        directories = domain_db.load_directories(self._domain)
        if directories:
            self.text.insert(tk.END, f"\nDirectories ({len(directories)}):\n", "info")
            for path, ts in directories:
                self.text.insert(tk.END, f"  {path}\n", "bright")

        web = domain_db.load_web_services(self._domain)
        if web:
            for port, output in web:
                self.text.insert(tk.END, f"\nWeb port {port}:\n", "info")
                for line in output.split("\n"):
                    self.text.insert(tk.END, f"  {line}\n", "bright")

        if machines:
            self._machine_rows = []
            self.text.insert(tk.END, f"\nMachines ({len(machines)}):\n", "info")
            for m in machines:
                row_start = int(self.text.index("end-1c").split(".")[0])
                self.text.insert(tk.END, f"  #{m['machine_id']:<4} {m['machine_ip']}", "bright")
                if m.get("source"):
                    self.text.insert(tk.END, f" ({m['source']})", "muted")
                self.text.insert(tk.END, "\n")
                self._machine_rows.append((row_start, m["machine_ip"]))
        else:
            self._machine_rows = []
            self.text.insert(tk.END, "\nMachines: (none)\n", "muted")

        self.text.configure(state=tk.DISABLED)
