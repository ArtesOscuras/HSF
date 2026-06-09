import os
import re
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from .base import BaseView
from src.machines import store, interface_name, interface_ip

MUTED = "#888888"
BRIGHT = "#ffffff"

ICON_SIZE = 32
COL_GAP = "   "

_icon_cache = {}


def _load_icons():
    global _icon_cache
    if _icon_cache:
        return
    icons_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons")
    icons_dir = os.path.abspath(icons_dir)
    if not os.path.isdir(icons_dir):
        return
    for fname in os.listdir(icons_dir):
        if not fname.lower().endswith(".png"):
            continue
        path = os.path.join(icons_dir, fname)
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
            name = os.path.splitext(fname)[0].lower()
            _icon_cache[name] = ImageTk.PhotoImage(img)
        except Exception:
            pass


class NetworkView(BaseView):
    name = "network"
    description = "Network monitoring and scanning"

    MIN_ID = 4
    MIN_HOSTNAME = 6

    def _build_ui(self):
        _load_icons()

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
            spacing1=6,
            spacing3=6,
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
        self.text.bind("<Button-1>", self._on_line_click)
        self.text.bind("<Motion>", self._on_mouse_move)
        self.after(100, self._poll)

    def on_deactivate(self):
        self.text.unbind("<Button-1>")
        self.text.unbind("<Motion>")
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self._machines = []

    @staticmethod
    def _is_local(m):
        return m.ip in ("127.0.0.1", "::1") or m.ip.startswith("127.")

    @staticmethod
    def _guess_icon(machine):
        dt = (machine.device_type or "device unknown").lower()
        for name in sorted(_icon_cache, key=lambda n: -len(n)):
            if name in dt or dt in name:
                return _icon_cache[name]
        return _icon_cache.get("device unknown")

    @staticmethod
    def _display_label(machine):
        label = machine.model if machine.model else (machine.device_type or "device unknown")
        return re.sub(r"\s+Build\s+\d+", "", label)

    def _insert_line(self, machine, w_id, w_device, w_hostname, center_pad):
        id_str = f"#{machine.id}" if machine.id else "#?"
        label = self._display_label(machine)
        hostname = machine.hostname or ""

        self.text.insert(tk.END, center_pad, "bright")
        self.text.insert(tk.END, id_str, "muted")
        self.text.insert(tk.END, " " * max(1, w_id - len(id_str)))
        self.text.insert(tk.END, COL_GAP, "bright")

        icon = self._guess_icon(machine)
        if icon:
            self.text.image_create(tk.END, image=icon)
        else:
            self.text.insert(tk.END, "?")
        self.text.insert(tk.END, COL_GAP, "bright")

        self.text.insert(tk.END, label, "bright")
        self.text.insert(tk.END, " " * max(1, w_device - len(label)))
        self.text.insert(tk.END, COL_GAP, "bright")

        self.text.insert(tk.END, hostname, "muted")
        self.text.insert(tk.END, " " * max(1, w_hostname - len(hostname)))
        self.text.insert(tk.END, COL_GAP, "bright")

        self.text.insert(tk.END, f"{machine.ip}\n", "bright")

    def _on_line_click(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0]) - 1
        if self._on_machine_click and 0 <= line < len(self._machines):
            self._on_machine_click(self._machines[line])
        return "break"

    def _on_mouse_move(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0]) - 1
        cursor = "hand2" if 0 <= line < len(self._machines) else ""
        self.text.configure(cursor=cursor)

    def _poll(self):
        self.iface_label.config(
            text=f"{interface_name}  {interface_ip}" if interface_name else ""
        )

        all_machines = store.get_all_sorted()
        machines = [m for m in all_machines if not self._is_local(m)]
        self._machines = machines

        w_id = self.MIN_ID
        w_device = 0
        w_hostname = self.MIN_HOSTNAME
        for m in machines:
            id_str = f"#{m.id}" if m.id else "#?"
            w_id = max(w_id, len(id_str))
            w_device = max(w_device, len(self._display_label(m)))
            w_hostname = max(w_hostname, len(m.hostname or ""))

        font = tkfont.Font(font=self.text.cget("font"))
        gap_px = font.measure(COL_GAP)

        row_content_px = (
            font.measure("M" * w_id) + gap_px
            + ICON_SIZE + gap_px
            + font.measure("M" * w_device) + gap_px
            + font.measure("M" * w_hostname) + gap_px
            + font.measure("255.255.255.255")
        )

        w = self.text.winfo_width()
        char_w = font.measure(" ")
        if w > row_content_px:
            pad_chars = int((w - row_content_px) // 2 // char_w)
            center_pad = " " * max(0, pad_chars)
        else:
            center_pad = "  "

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        for m in machines:
            self._insert_line(m, w_id, w_device, w_hostname, center_pad)

        self.text.configure(state=tk.DISABLED)

        self._poll_id = self.after(2000, self._poll)
