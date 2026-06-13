import json
import os
import tkinter as tk
from .base import BaseView

MUTED = "#888888"
BRIGHT = "#ffffff"
INFO = "#5ba3ec"
SUCCESS = "#00cc66"


def _get_evidence_dir():
    base = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    return os.path.abspath(base)


def _load_evidence(name):
    base = _get_evidence_dir()
    session_path = os.path.join(base, name, "session.json")
    if not os.path.isfile(session_path):
        return None
    with open(session_path) as f:
        return json.load(f)


def _list_requests(name):
    base = _get_evidence_dir()
    target_dir = os.path.join(base, name)
    results = []
    if os.path.isdir(target_dir):
        for rdir in sorted(os.listdir(target_dir)):
            rpath = os.path.join(target_dir, rdir)
            if os.path.isdir(rpath):
                req_f = os.path.join(rpath, "request.json")
                resp_f = os.path.join(rpath, "response.json")
                if os.path.isfile(req_f):
                    with open(req_f) as f:
                        req = json.load(f)
                else:
                    req = {}
                if os.path.isfile(resp_f):
                    with open(resp_f) as f:
                        resp = json.load(f)
                else:
                    resp = {}
                results.append((req, resp))
    return results


class EvidenceDetailView(BaseView):
    name = "evidence_detail"
    description = "Evidence session detail"

    def __init__(self, parent, ev_name, **kwargs):
        self._ev_name = ev_name
        super().__init__(parent, **kwargs)
        super().__init__(parent, **kwargs)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 10))

        self._title_label = tk.Label(
            header, text="",
            font=("Menlo", 22, "bold"),
            fg="#ffffff", bg="#000000",
        )
        self._title_label.pack(anchor="center")
        self._title_label.bind("<Button-1>", self._on_title_click)
        self._title_label.bind("<Enter>", lambda e: self._title_label.config(font=("Menlo", 22, "bold", "underline")))
        self._title_label.bind("<Leave>", lambda e: self._title_label.config(font=("Menlo", 22, "bold")))
        self._on_back_click = None

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew", padx=(220, 20), pady=(0, 20))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            bg="#000000", fg=BRIGHT,
            font=("Menlo", 13), borderwidth=0, highlightthickness=0,
            state=tk.DISABLED, cursor="", wrap=tk.WORD,
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
        self.text.tag_configure("success", foreground=SUCCESS)

    def on_activate(self):
        self._refresh()

    def on_deactivate(self):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.configure(state=tk.DISABLED)

    def _on_title_click(self, event):
        if self._on_back_click:
            self._on_back_click()

    def _refresh(self):
        meta = _load_evidence(self._ev_name)
        reqs = _list_requests(self._ev_name)

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        self._title_label.config(text=f"Evidence — {self._ev_name}")

        if not meta:
            self.text.insert(tk.END, "No session data found.\n", "muted")
            self.text.configure(state=tk.DISABLED)
            return

        rows = [
            ("Target", meta.get("target", "")),
            ("Browser", meta.get("browser", "")),
            ("Started", (meta.get("started_at", "") or "")[:19].replace("T", " ")),
            ("Ended", (meta.get("ended_at", "") or "")[:19].replace("T", " ")),
            ("Requests", str(meta.get("request_count", 0))),
        ]
        label_w = max(len(r[0]) for r in rows) + 2
        for label, value in rows:
            self.text.insert(tk.END, f"  {label + ':':<{label_w}} ", "muted")
            self.text.insert(tk.END, f"{value or '-'}\n", "bright")

        navs = meta.get("navigations", [])
        if navs:
            self.text.insert(tk.END, f"\nNavigations ({len(navs)}):\n", "info")
            for n in navs:
                self.text.insert(tk.END, f"  {n['url']}\n", "bright")

        certs = meta.get("certificates", [])
        if certs:
            self.text.insert(tk.END, f"\nCertificates ({len(certs)}):\n", "info")
            for c in certs:
                self.text.insert(tk.END, f"  Subject: {c.get('subject', '')}\n", "bright")
                self.text.insert(tk.END, f"  Issuer:  {c.get('issuer', '')}\n", "muted")
                protocol = c.get("protocol", "")
                if protocol:
                    self.text.insert(tk.END, f"  Protocol: {protocol}\n", "muted")
                sans = c.get("sanList", [])
                if sans:
                    self.text.insert(tk.END, f"  SAN: {', '.join(sans)}\n", "muted")
                self.text.insert(tk.END, "\n")

        cookies_req = {}
        cookies_resp = {}
        for req, resp in reqs:
            for c in req.get("cookies", []):
                key = (c.get("name", ""), c.get("value", ""))
                if key[0]:
                    cookies_req[key] = c
            for c in resp.get("cookies", []):
                key = (c.get("name", ""), c.get("value", ""))
                if key[0]:
                    cookies_resp[key] = c
        if cookies_req or cookies_resp:
            self.text.insert(tk.END, f"\nCookies:\n", "info")
            all_names = sorted(set(c.get("name", "") for c in cookies_req.values())
                              | set(c.get("name", "") for c in cookies_resp.values()))
            for name in all_names:
                c = next((x for x in cookies_resp.values() if x.get("name") == name), None)
                c = c or next((x for x in cookies_req.values() if x.get("name") == name), None)
                if not c:
                    continue
                self.text.insert(tk.END, f"  {name:<20} ", "bright")
                val = c.get("value", "")
                if len(val) > 60:
                    val = val[:60] + "..."
                self.text.insert(tk.END, f"{val}\n", "muted")

        if reqs:
            self.text.insert(tk.END, f"\nCaptured requests ({len(reqs)}):\n", "info")
            for req, resp in reqs:
                method = req.get("method", "?")
                url = req.get("url", "")
                if len(url) > 50:
                    url = url[:50] + "..."
                status = resp.get("status", "?")
                tag = "success" if status != 0 else "error"
                self.text.insert(tk.END, f"  [{status}] {method} {url}\n", tag)

        self.text.configure(state=tk.DISABLED)
