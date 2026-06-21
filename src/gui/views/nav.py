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
_zoom_label = None


def build(parent, active_view, navigator):
    global _frame, _btns, _zoom_label
    _frame = tk.Frame(parent, bg="#000000")
    _frame.pack(pady=(0, 10), fill=tk.X)
    _btns = []

    zoom_frame = tk.Frame(_frame, bg="#000000")
    zoom_frame.pack(side=tk.RIGHT, padx=(0, 5))

    minus_btn = tk.Label(
        zoom_frame, text="\u2212", bg="#222222", fg="#ffffff",
        font=fonts.view_font(11),
        padx=6, pady=2,
    )
    minus_btn.pack(side=tk.LEFT)
    minus_btn.bind("<Button-1>", lambda e: _zoom(-0.1))
    minus_btn.bind("<Enter>", lambda e: minus_btn.config(bg="#333333"))
    minus_btn.bind("<Leave>", lambda e: minus_btn.config(bg="#222222"))

    _zoom_label = tk.Label(
        zoom_frame, text="100%", bg="#000000", fg="#888888",
        font=fonts.view_font(10),
        padx=6,
    )
    _zoom_label.pack(side=tk.LEFT)

    plus_btn = tk.Label(
        zoom_frame, text="+", bg="#222222", fg="#ffffff",
        font=fonts.view_font(11),
        padx=6, pady=2,
    )
    plus_btn.pack(side=tk.LEFT)
    plus_btn.bind("<Button-1>", lambda e: _zoom(+0.1))
    plus_btn.bind("<Enter>", lambda e: plus_btn.config(bg="#333333"))
    plus_btn.bind("<Leave>", lambda e: plus_btn.config(bg="#222222"))

    # Phantom left spacer matching zoom width for symmetry
    tk.Frame(_frame, bg="#000000", width=75).pack(side=tk.LEFT)
    tk.Frame(_frame, bg="#000000").pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    inner = tk.Frame(_frame, bg="#000000")
    inner.pack(side=tk.LEFT)

    for text, view_name in _ORDER:
        is_active = view_name == active_view
        normal = fonts.view_font_bold(11) if is_active else fonts.view_font(11)
        hover = fonts.view_font_bold_under(11) if is_active else fonts.view_font_under(11)
        btn = tk.Label(
            inner, text=f"  {text}  ",
            font=normal,
            fg="#ffffff" if is_active else "#888888",
            bg="#000000",
        )
        btn.pack(side=tk.LEFT, padx=5)
        btn.bind("<Button-1>", lambda e, vn=view_name: navigator.activate_view(vn))
        btn.bind("<Enter>", lambda e, b=btn, h=hover: b.config(font=h))
        btn.bind("<Leave>", lambda e, b=btn, n=normal: b.config(font=n))
        _btns.append(btn)

    tk.Frame(_frame, bg="#000000").pack(side=tk.LEFT, fill=tk.BOTH, expand=True)


def _zoom(delta):
    from src.settings import set as _set_setting, save as _save_settings
    fonts.set_view_scale(fonts.view_scale() + delta)
    _update_label()
    _set_setting("view_scale", fonts.view_scale())
    _save_settings()


def set_initial_zoom(scale):
    fonts.set_view_scale(scale)
    _update_label()


def _update_label():
    global _zoom_label
    if _zoom_label:
        _zoom_label.config(text=f"{int(fonts.view_scale() * 100)}%")


def refresh():
    if not _btns:
        return
    for btn in _btns:
        btn.pack_forget()
    for btn in _btns:
        btn.pack(side=tk.LEFT, padx=5)
