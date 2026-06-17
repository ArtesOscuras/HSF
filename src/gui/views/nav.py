import tkinter as tk
from src.gui import fonts

_ORDER = [
    ("Tools", "tools"),
    ("Machines", "machines"),
    ("Domains", "domains"),
    ("Shells", "shells"),
    ("Credentials", "credentials"),
    ("Evidences", "evidences"),
]

_frame = None
_btns = []


def build(parent, active_view, navigator):
    global _frame, _btns
    _frame = tk.Frame(parent, bg="#000000")
    _frame.pack(pady=(0, 10))
    _btns = []

    for text, view_name in _ORDER:
        is_active = view_name == active_view
        normal = fonts.view_font_bold(11) if is_active else fonts.view_font(11)
        hover = fonts.view_font_bold_under(11) if is_active else fonts.view_font_under(11)
        btn = tk.Label(
            _frame, text=f"  {text}  ",
            font=normal,
            fg="#ffffff" if is_active else "#888888",
            bg="#000000",
        )
        btn.pack(side=tk.LEFT, padx=5)
        btn.bind("<Button-1>", lambda e, vn=view_name: navigator.activate_view(vn))
        btn.bind("<Enter>", lambda e, b=btn, h=hover: b.config(font=h))
        btn.bind("<Leave>", lambda e, b=btn, n=normal: b.config(font=n))
        _btns.append(btn)


def refresh():
    if not _btns:
        return
    for btn in _btns:
        btn.pack_forget()
    for btn in _btns:
        btn.pack(side=tk.LEFT, padx=5)
