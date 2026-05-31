import tkinter as tk


class BaseView(tk.Frame):
    name = "base"
    description = "Base view"

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#000000", **kwargs)
        self.grid_propagate(False)
        self._build_ui()

    def _build_ui(self):
        raise NotImplementedError

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass
