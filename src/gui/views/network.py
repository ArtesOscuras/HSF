import tkinter as tk
import tkinter.font as tkfont
from .base import BaseView
from src.machines import store, interface_name, interface_ip


ICONS = {
    "default": "\U0001F4BB",
}


class NetworkView(BaseView):
    name = "network"
    description = "Network monitoring and scanning"

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        tk.Label(
            header,
            text="Devices",
            font=("Menlo", 22, "bold"),
            fg="#ffffff",
            bg="#000000",
        ).pack(anchor="center")

        self.iface_label = tk.Label(
            header,
            text="",
            font=("Menlo", 11),
            fg="#c0c0c0",
            bg="#000000",
        )
        self.iface_label.pack(anchor="center")

        list_frame = tk.Frame(self, bg="#000000")
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_frame,
            bg="#000000",
            fg="#bdfd01",
            selectbackground="#1a3300",
            selectforeground="#bdfd01",
            font=("Menlo", 18),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        self._poll_id = None

    def on_activate(self):
        self._poll()

    def on_deactivate(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    @staticmethod
    def _is_local(m):
        return m.ip in ("127.0.0.1", "::1") or m.ip.startswith("127.")

    @staticmethod
    def _guess_icon(machine):
        return ICONS["default"]

    @staticmethod
    def _guess_type(machine):
        return machine.device_type if machine.device_type else "device unknown"

    def _center_padding(self):
        w = self.listbox.winfo_width()
        if w < 50:
            return " " * 5
        font = tkfont.Font(font=self.listbox.cget("font"))
        sample = f"{ICONS['default']}   Windows machine   255.255.255.255"
        content_px = font.measure(sample)
        char_width = font.measure(" ")
        padding_px = max(5, (w - content_px) // 2)
        return " " * max(1, padding_px // char_width)

    def _format_line(self, machine, padding):
        return f"{padding}{self._guess_icon(machine)}   {self._guess_type(machine)}   {machine.ip}"

    def _poll(self):
        padding = self._center_padding()

        self.iface_label.config(
            text=f"{interface_name}  {interface_ip}" if interface_name else ""
        )

        all_machines = store.get_all_sorted()
        machines = [m for m in all_machines if not self._is_local(m)]

        current_count = self.listbox.size()
        if current_count != len(machines):
            self.listbox.delete(0, tk.END)
            for m in machines:
                self.listbox.insert(tk.END, self._format_line(m, padding))
        else:
            for i, m in enumerate(machines):
                self.listbox.delete(i)
                self.listbox.insert(i, self._format_line(m, padding))

        self._poll_id = self.after(2000, self._poll)
