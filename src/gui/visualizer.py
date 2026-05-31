import tkinter as tk
from .views import BaseView


class Visualizer(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#000000", **kwargs)
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.views = {}
        self._active_view_name = None
        self._active_view = None

        self._placeholder = tk.Label(
            self,
            text="Visualization Area",
            font=("Menlo", 18),
            fg="#8cba02",
            bg="#000000",
        )
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

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
