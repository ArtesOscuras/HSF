import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk

SUCCESS = "#00cc66"
FAIL = "#f44747"
WARN = "#ce9178"
BRIGHT = "#ffffff"
MUTED = "#888888"
INFO = "#5ba3ec"

_checks_order = []


def _checks():
    # --- System ---
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    yield _check("root", "Root", lambda: is_root, kind="system", critical=False,
                 detail="yes" if is_root else "no")
    yield _check("python_version", f"Python {platform.python_version()}",
                 lambda: sys.version_info >= (3, 8),
                 kind="system", critical=True)

    # --- Python dependencies ---
    yield _check("scapy", "scapy", lambda: _has_module("scapy"), kind="python", critical=True)
    yield _check("zeroconf", "zeroconf", lambda: _has_module("zeroconf"), kind="python", critical=True)
    yield _check("impacket", "impacket", lambda: _has_module("impacket"), kind="python", critical=True)
    yield _check("websocket", "websocket-client", lambda: _has_module("websocket"), kind="python", critical=True)
    yield _check("pillow", "Pillow", lambda: _has_module("PIL"), kind="python", critical=True)
    yield _check("netifaces", "netifaces", lambda: _has_module("netifaces"), kind="python", critical=True)
    yield _check("python_nmap", "python-nmap", lambda: _has_module("nmap"), kind="python", critical=False)

    # --- Binaries ---
    yield _check("nmap_bin", "nmap", lambda: _resolve_binary("nmap")[0], kind="binary", critical=False)
    yield _check("hashcat", "hashcat", lambda: _resolve_binary("hashcat")[0], kind="binary", critical=False)
    yield _check("hydra", "hydra", lambda: _resolve_binary("hydra")[0], kind="binary", critical=False)
    yield _check("whatweb", "whatweb", lambda: _resolve_binary("whatweb")[0], kind="binary", critical=False)
    yield _check("browsers", "Chromium browser", lambda: _browser_check()[0], kind="binary", critical=False)


def _check(key, label, fn, kind="", critical=False, detail=""):
    return {"key": key, "label": label, "fn": fn, "kind": kind, "critical": critical, "detail": detail}


def _has_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _resolve_binary(name):
    """Find a binary using 3 levels: PATH, shell rc file aliases, interactive shell."""
    # Level 1 — standard PATH
    found = shutil.which(name)
    if found:
        return True, found

    # Level 2 — parse shell rc file for aliases
    found = _parse_rc_for_binary(name)
    if found:
        return True, found

    # Level 3 — interactive shell fallback
    found = _find_via_interactive_shell(name)
    if found:
        return True, found

    return False, ""


def _shell_rc_file():
    shell = os.environ.get("SHELL", "")
    home = os.path.expanduser("~")
    candidates = []
    if "zsh" in shell:
        candidates = [os.path.join(home, ".zshrc")]
    elif "bash" in shell:
        candidates = [os.path.join(home, ".bashrc"), os.path.join(home, ".bash_profile")]
    candidates.append(os.path.join(home, ".zshrc"))
    candidates.append(os.path.join(home, ".bashrc"))
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.R_OK):
            return c
    return None


def _parse_rc_for_binary(name):
    rc_file = _shell_rc_file()
    if not rc_file:
        return ""

    try:
        with open(rc_file) as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return ""

    # Find alias definitions: alias name='/path' or alias name="/path"
    for pattern in [
        rf"alias\s+{re.escape(name)}\s*=\s*'([^']+)'",
        rf'alias\s+{re.escape(name)}\s*=\s*"([^"]+)"',
    ]:
        m = re.search(pattern, content)
        if m:
            path = m.group(1).strip()
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

    # Find PATH exports and scan those dirs
    for pattern in [
        r'export\s+PATH\s*=\s*"([^"]+)"',
        r"export\s+PATH\s*=\s*'([^']+)'",
        r'export\s+PATH\s*=\s*([^\n]+)',
    ]:
        for m in re.finditer(pattern, content):
            extra_paths = m.group(1).strip()
            for p in extra_paths.split(":"):
                p = os.path.expandvars(p.strip())
                candidate = os.path.join(p, name)
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    return candidate

    return ""


def _find_via_interactive_shell(name):
    shell = os.environ.get("SHELL", "/bin/sh")
    shell_name = os.path.basename(shell)
    try:
        r = subprocess.run(
            [shell, "-ic", f"command -v {name}"],
            capture_output=True, timeout=5, text=True,
        )
        out = r.stdout.strip()
        if out and os.path.isfile(out):
            return out
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _browser_check():
    from src.tools.webrecorder.browsers import find_browsers
    browsers = find_browsers()
    if browsers:
        return True, list(browsers.keys())[0]
    return False, ""


def run_checks():
    results = []
    for item in _checks():
        try:
            result = item["fn"]()
            results.append({"key": item["key"], "label": item["label"],
                           "ok": result, "kind": item.get("kind", ""),
                           "critical": item["critical"], "detail": item.get("detail", "")})
        except Exception as e:
            results.append({"key": item["key"], "label": item["label"],
                           "ok": False, "kind": item.get("kind", ""),
                           "critical": item["critical"], "detail": item.get("detail", ""),
                           "error": str(e)})
    return results


class InitDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("HSF — Initialization Check")
        self.geometry("780x620")
        self.configure(bg="#111111")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        header = tk.Frame(self, bg="#111111")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5), padx=15)

        tk.Label(
            header,
            text="System Checks",
            font=("Menlo", 18, "bold"),
            fg=BRIGHT,
            bg="#111111",
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Checking dependencies and system capabilities...",
            font=("Menlo", 10),
            fg=MUTED,
            bg="#111111",
        ).pack(anchor="w", pady=(2, 0))

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 10))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            bg="#000000",
            fg=BRIGHT,
            font=("Menlo", 11),
            borderwidth=0,
            highlightthickness=0,
            state=tk.DISABLED,
            cursor="",
            wrap=tk.WORD,
            pady=8,
            padx=10,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.tag_configure("success", foreground=SUCCESS)
        self.text.tag_configure("fail", foreground=FAIL)
        self.text.tag_configure("warn", foreground=WARN)
        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("bright", foreground=BRIGHT)
        self.text.tag_configure("info", foreground=INFO)
        self.text.tag_configure("bold", font=("Menlo", 11, "bold"))

        btn_frame = tk.Frame(self, bg="#111111")
        btn_frame.grid(row=2, column=0, pady=(0, 15))

        self._ok_btn = tk.Label(
            btn_frame, text="     Continue     ", bg="#222222", fg=BRIGHT,
            font=("Menlo", 12, "bold"), relief=tk.RAISED, bd=1,
            padx=20, pady=8,
        )
        self._ok_btn.pack()
        self._ok_btn.bind("<Button-1>", lambda e: self.destroy())
        self._ok_btn.bind("<Enter>", lambda e: self._ok_btn.config(bg="#333333"))
        self._ok_btn.bind("<Leave>", lambda e: self._ok_btn.config(bg="#222222"))

        self._failed_critical = False
        self._total = 0
        self._done = 0

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(50, self._start_checks)

    def _start_checks(self):
        threading.Thread(target=self._run_checks, daemon=True).start()

    def _run_checks(self):
        results = run_checks()
        self._total = len(results)
        self._done = 0
        self._failed_critical = False
        self._last_kind = None

        for r in results:
            self._done += 1
            self._show_result(r)

        self.after(0, self._finish)

    def _show_result(self, r):
        def _insert():
            self.text.configure(state=tk.NORMAL)
            key = r["key"]
            label = r["label"]
            ok = r["ok"]
            critical = r["critical"]
            kind = r.get("kind", "")

            if kind and kind != self._last_kind:
                self._last_kind = kind
                self.text.insert(tk.END, "\n", "bright")
                self.text.insert(tk.END, f"  \u2500\u2500 {kind.upper()} \u2500\u2500\n", "info")
                self.text.insert(tk.END, "\n", "bright")

            line = f"  [{self._done}/{self._total}] "
            self.text.insert(tk.END, line, "muted")

            if ok:
                marker = "[OK]"
                tag = "success"
            elif critical:
                marker = "[FAIL]"
                tag = "fail"
                self._failed_critical = True
            else:
                marker = "[WARN]"
                tag = "warn"

            self.text.insert(tk.END, f"{marker} ", tag)
            self.text.insert(tk.END, f"{label}", "bright")
            if r.get("detail"):
                self.text.insert(tk.END, f" : {r['detail']}", "info")
            self.text.insert(tk.END, "\n")
            if r.get("kind"):
                self.text.insert(tk.END, f"        ({r['kind']})\n", "muted")

            if "error" in r:
                self.text.insert(tk.END, f"        {r['error']}\n", "fail")

            self.text.see(tk.END)
            self.text.configure(state=tk.DISABLED)

            from src.info import set as info_set
            info_set(key, ok)

        self.after(0, _insert)

    def _finish(self):
        def _ui():
            self.text.configure(state=tk.NORMAL)
            self.text.insert(tk.END, "\n")
            self.text.insert(tk.END, "\u2500" * 58 + "\n", "muted")
            if self._failed_critical:
                self.text.insert(tk.END, "  WARNING: Critical dependencies missing!\n", "fail")
                self.text.insert(tk.END, "  Some features will not work properly.\n", "warn")
            else:
                passed = self._total
                self.text.insert(tk.END, f"  All {passed} checks complete.", "success")
            self.text.insert(tk.END, "\n")
            self.text.see(tk.END)
            self.text.configure(state=tk.DISABLED)
            self._ok_btn.config(text="     Continue     ")

        self.after(0, _ui)
