import tkinter as tk
from src.gui import fonts
from .views import BaseView


class Visualizer(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#000000", **kwargs)
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)

        self.views = {}
        self._active_view_name = None
        self._active_view = None

        self._placeholder = tk.Label(
            self,
            text="Visualization Area",
            font=(fonts.family(), 18),
            fg="#888888",
            bg="#000000",
        )
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

        self._build_zoom_controls()

    def _build_zoom_controls(self):
        zoom_frame = tk.Frame(self, bg="#111111", width=28)
        zoom_frame.grid(row=0, column=1, sticky="ns", padx=(0, 2))
        zoom_frame.grid_propagate(False)

        plus_btn = tk.Label(
            zoom_frame, text="  +  ", bg="#222222", fg="#ffffff",
            font=(fonts.family(), 14), cursor="hand2",
        )
        plus_btn.pack(side=tk.TOP, pady=(10, 2))
        plus_btn.bind("<Button-1>", lambda e: self._zoom(+0.1))
        plus_btn.bind("<Enter>", lambda e: plus_btn.config(bg="#333333"))
        plus_btn.bind("<Leave>", lambda e: plus_btn.config(bg="#222222"))

        self._zoom_label = tk.Label(
            zoom_frame, text="100%", bg="#111111", fg="#888888",
            font=(fonts.family(), 9),
        )
        self._zoom_label.pack(side=tk.TOP, pady=2)

        minus_btn = tk.Label(
            zoom_frame, text="  -  ", bg="#222222", fg="#ffffff",
            font=(fonts.family(), 14), cursor="hand2",
        )
        minus_btn.pack(side=tk.TOP, pady=(2, 10))
        minus_btn.bind("<Button-1>", lambda e: self._zoom(-0.1))
        minus_btn.bind("<Enter>", lambda e: minus_btn.config(bg="#333333"))
        minus_btn.bind("<Leave>", lambda e: minus_btn.config(bg="#222222"))

    def _zoom(self, delta):
        old = fonts.view_scale()
        fonts.set_view_scale(old + delta)
        self._zoom_label.config(text=f"{int(fonts.view_scale() * 100)}%")
        if self._active_view:
            self._active_view.on_zoom()
        from src.gui.views.nav import refresh as _nav_refresh
        _nav_refresh()
        self.update_idletasks()
        from src.settings import set as _set_setting, save as _save_settings
        _set_setting("view_scale", fonts.view_scale())
        _save_settings()

    def set_initial_zoom(self, scale):
        fonts.set_view_scale(scale)
        self._zoom_label.config(text=f"{int(fonts.view_scale() * 100)}%")
        self.update_idletasks()

    def register_view(self, name, view):
        self.views[name] = view

    def get_view_names(self):
        return list(self.views.keys())

    def get_view(self, name):
        return self.views.get(name)

    def get_active_view(self):
        return self._active_view

    def get_active_view_name(self):
        return self._active_view_name

    def activate_view(self, name):
        if name not in self.views:
            raise ValueError(f"Unknown view: {name}")

        if self._active_view:
            self._active_view.on_deactivate()
            self._active_view.grid_forget()

        self._placeholder.place_forget()

        self._active_view_name = name
        self._active_view = self.views[name]
        self._active_view.grid(row=0, column=0, sticky="nsew")
        self._active_view.on_activate()
