import os
import platform
import shutil
import tkinter as tk

_BROWSERS = {
    "google-chrome": ("Google Chrome", [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    ]),
    "google-chrome-stable": ("Google Chrome", []),
    "chromium": ("Chromium", [
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "C:\\Program Files\\Chromium\\Application\\chrome.exe",
    ]),
    "chromium-browser": ("Chromium", []),
    "brave-browser": ("Brave", [
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
    ]),
    "brave": ("Brave", []),
    "microsoft-edge": ("Microsoft Edge", [
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    ]),
    "edge": ("Microsoft Edge", []),
}


def _find_in_known_paths(extra_paths):
    for p in extra_paths:
        if os.path.isfile(p):
            return p
    return None


def find_browsers():
    found = {}
    seen = set()
    for binary, (label, extra_paths) in _BROWSERS.items():
        path = shutil.which(binary)
        if not path and extra_paths:
            path = _find_in_known_paths(extra_paths)
        if path and label not in seen:
            found[path] = label
            seen.add(label)
    return found


class BrowserSelector(tk.Toplevel):
    def __init__(self, parent, browsers):
        super().__init__(parent)
        self.result = None

        self.title("Select Browser")
        self.geometry("450x280")
        self.configure(bg="#111111")

        self.transient(parent)
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        tk.Label(
            self, text="Multiple browsers detected. Select one:",
            font=("Menlo", 11), fg="#ffffff", bg="#111111",
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        frame = tk.Frame(self, bg="#000000")
        frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._listbox = tk.Listbox(
            frame, bg="#000000", fg="#ffffff",
            selectbackground="#333333", selectforeground="#ffffff",
            font=("Menlo", 12), borderwidth=0, highlightthickness=0,
            activestyle="none",
        )
        self._listbox.grid(row=0, column=0, sticky="nsew")

        self._paths = []
        for path, label in sorted(browsers.items()):
            self._listbox.insert(tk.END, f"  {label}  ({path})")
            self._paths.append(path)

        if self._paths:
            self._listbox.selection_set(0)

        self._listbox.bind("<Return>", lambda e: self._select())
        self._listbox.bind("<Double-Button-1>", lambda e: self._select())
        self._listbox.focus_set()

        btn_frame = tk.Frame(self, bg="#111111")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 15))

        cancel_btn = tk.Label(
            btn_frame, text="  Cancel  ", bg="#222222", fg="#ffffff",
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6, cursor="",
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
        cancel_btn.bind("<Button-1>", lambda e: self.destroy())
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg="#333333"))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg="#222222"))

        select_btn = tk.Label(
            btn_frame, text="  Select  ", bg="#222222", fg="#ffffff",
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6, cursor="",
        )
        select_btn.pack(side=tk.RIGHT)
        select_btn.bind("<Button-1>", lambda e: self._select())
        select_btn.bind("<Enter>", lambda e: select_btn.config(bg="#333333"))
        select_btn.bind("<Leave>", lambda e: select_btn.config(bg="#222222"))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    def _select(self):
        sel = self._listbox.curselection()
        if sel:
            self.result = self._paths[sel[0]]
        self.destroy()
