import re
import tkinter as tk
import tkinter.font as tkfont
from .base import BaseView
from src.machines import store, interface_name, interface_ip

MUTED = "#888888"
BRIGHT = "#ffffff"

ICONS = {
    "default": "\U0001F4BB",
}


class NetworkView(BaseView):
    name = "network"
    description = "Network monitoring and scanning"

    DEVICE_WIDTH = 22
    HOSTNAME_WIDTH = 28

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
            fg=MUTED,
            bg="#000000",
        )
        self.iface_label.pack(anchor="center")

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            bg="#000000",
            fg=BRIGHT,
            font=("Menlo", 16),
            borderwidth=0,
            highlightthickness=0,
            pady=10,
            state=tk.DISABLED,
            wrap=tk.NONE,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("bright", foreground=BRIGHT)

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

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
    def _display_label(machine):
        label = machine.model if machine.model else (machine.device_type or "device unknown")
        return re.sub(r"\s+Build\s+\d+", "", label)

    def _center_padding(self):
        w = self.text.winfo_width()
        if w < 50:
            return " " * 3
        font = tkfont.Font(font=self.text.cget("font"))
        sample = f"{ICONS['default']}   {'M' * self.DEVICE_WIDTH}{'M' * self.HOSTNAME_WIDTH}255.255.255.255"
        content_px = font.measure(sample)
        char_width = font.measure(" ")
        padding_px = max(5, (w - content_px) // 2)
        return " " * max(1, padding_px // char_width)

    def _insert_line(self, machine, center_pad):
        self.text.insert(tk.END, center_pad, "bright")
        self.text.insert(tk.END, "    ", "bright")
        icon = self._guess_icon(machine)
        self.text.insert(tk.END, f"{icon}   ", "bright")

        label = self._display_label(machine)
        self.text.insert(tk.END, label, "bright")
        pad = max(1, self.DEVICE_WIDTH - len(label))
        self.text.insert(tk.END, " " * pad)

        hostname = machine.hostname if machine.hostname else ""
        self.text.insert(tk.END, hostname, "muted")
        pad2 = max(1, self.HOSTNAME_WIDTH - len(hostname))
        self.text.insert(tk.END, " " * pad2)

        self.text.insert(tk.END, f"{machine.ip}\n", "bright")

    def _poll(self):
        self.iface_label.config(
            text=f"{interface_name}  {interface_ip}" if interface_name else ""
        )

        all_machines = store.get_all_sorted()
        machines = [m for m in all_machines if not self._is_local(m)]

        center_pad = self._center_padding()

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        for m in machines:
            self._insert_line(m, center_pad)

        self.text.configure(state=tk.DISABLED)

        self._poll_id = self.after(2000, self._poll)
