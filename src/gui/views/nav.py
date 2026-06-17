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


def build(parent, active_view, navigator):
    frame = tk.Frame(parent, bg="#000000")
    frame.pack(pady=(0, 10))

    for text, view_name in _ORDER:
        is_active = view_name == active_view
        base_font = fonts.view_font_bold(11) if is_active else fonts.view_font(11)
        btn = tk.Label(
            frame, text=f"  {text}  ",
            font=base_font,
            fg="#ffffff" if is_active else "#888888",
            bg="#000000",
        )
        btn.pack(side=tk.LEFT, padx=5)
        btn.bind("<Button-1>", lambda e, vn=view_name: navigator.activate_view(vn))
        btn.bind("<Enter>", lambda e, b=btn, a=is_active: b.config(
            font=fonts.view_font_bold_under(11) if a else fonts.view_font_under(11)))
        btn.bind("<Leave>", lambda e, b=btn, a=is_active: b.config(
            font=fonts.view_font_bold(11) if a else fonts.view_font(11)))
