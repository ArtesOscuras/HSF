import os
import re
import shutil
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from .base import BaseView
from src.machines import store, interface_name, interface_ip
from src.machines import machine_db

MUTED = "#888888"
BRIGHT = "#ffffff"

ICON_SIZE = 50
COL_GAP = "   "

_icon_cache = {}
_delete_img = None


def _load_delete_img():
    global _delete_img
    if _delete_img is not None:
        return _delete_img
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons", "delete.png")
    path = os.path.abspath(path)
    if os.path.isfile(path):
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((20, 20), Image.LANCZOS)
            _delete_img = ImageTk.PhotoImage(img)
        except Exception:
            _delete_img = False
    else:
        _delete_img = False
    return _delete_img


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
    name = "machines"
    description = "Discovered machines"

    MIN_ID = 4
    MIN_HOSTNAME = 6

    def _nav_btn(self, text, view_name, parent, active):
        btn = tk.Label(
            parent, text=f"  {text}  ",
            font=("Menlo", 11, "bold") if active else ("Menlo", 11),
            fg="#ffffff" if active else "#888888",
            bg="#000000",
        )
        btn.pack(side=tk.LEFT, padx=5)
        btn.bind("<Button-1>", lambda e: self.master.activate_view(view_name))
        btn.bind("<Enter>", lambda e: btn.config(font=("Menlo", 11, "bold", "underline") if active else ("Menlo", 11, "underline")))
        btn.bind("<Leave>", lambda e: btn.config(font=("Menlo", 11, "bold") if active else ("Menlo", 11)))

    def _build_ui(self):
        _load_icons()
        _load_delete_img()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        nav_frame = tk.Frame(header, bg="#000000")
        nav_frame.pack(pady=(0, 10))

        self._nav_btn("Machines", "machines", nav_frame, True)
        self._nav_btn("Domains", "domains", nav_frame, False)
        self._nav_btn("Evidences", "evidences", nav_frame, False)
        self._nav_btn("Credentials", "credentials", nav_frame, False)

        tk.Label(
            header,
            text="Machines",
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
            cursor="",
            wrap=tk.NONE,
            spacing1=8,
            spacing3=8,
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
        self.after(100, self._poll)

    def on_deactivate(self):
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
        if dt == "device unknown":
            return _icon_cache.get("question")
        for name in sorted(_icon_cache, key=lambda n: -len(n)):
            if name in dt or dt in name:
                return _icon_cache[name]
        return _icon_cache.get("question")

    @staticmethod
    def _display_label(machine):
        label = machine.model if machine.model else (machine.device_type or "device unknown")
        return re.sub(r"\s+Build\s+\d+", "", label)

    def _insert_line(self, machine, center_pad):
        id_str = f"#{machine.id}" if machine.id else "#?"
        label = self._display_label(machine)
        hostname = machine.hostname or ""

        self.text.insert(tk.END, center_pad, "bright")
        self.text.insert(tk.END, id_str, "muted")
        self.text.insert(tk.END, "\t", "bright")

        icon = self._guess_icon(machine)
        if icon:
            self.text.image_create(tk.END, image=icon)
        else:
            self.text.insert(tk.END, "?")
        self.text.insert(tk.END, "\t", "bright")

        tag = f"m_{machine.ip}"
        self.text.tag_configure(tag, underline=False)
        self.text.insert(tk.END, label[:40] + "\u2026" if len(label) > 40 else label, ("bright", tag))
        self.text.tag_bind(tag, "<Button-1>", lambda e, m=machine: (
            self._on_machine_click and self._on_machine_click(m)))
        self.text.tag_bind(tag, "<Enter>", lambda e, t=tag: self.text.tag_configure(t, underline=True))
        self.text.tag_bind(tag, "<Leave>", lambda e, t=tag: self.text.tag_configure(t, underline=False))
        self.text.insert(tk.END, "\t", "bright")

        self.text.insert(tk.END, hostname[:30] + "\u2026" if len(hostname) > 30 else hostname, "muted")
        self.text.insert(tk.END, "\t", "bright")

        self.text.insert(tk.END, f"{machine.ip}", "bright")
        self.text.insert(tk.END, "\t", "bright")

        del_img = _load_delete_img()
        if del_img:
            self.text.image_create(tk.END, image=del_img)
            del_tag = f"del_{machine.ip}"
            self.text.tag_add(del_tag, "end-2c", "end-1c")
            self.text.tag_bind(del_tag, "<Button-1>", lambda e, m=machine: (
                self._delete_machine(m), "break")[-1])

        self.text.insert(tk.END, "\n", "bright")

    def _delete_machine(self, machine):
        machine_db.delete_machine_db(machine.id)
        store.remove(machine.ip)

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
        w_ip = 7
        for m in machines:
            id_str = f"#{m.id}" if m.id else "#?"
            w_id = max(w_id, len(id_str))
            w_device = max(w_device, len(self._display_label(m)))
            w_hostname = max(w_hostname, len(m.hostname or ""))
            w_ip = max(w_ip, len(m.ip))

        font = tkfont.Font(font=self.text.cget("font"))
        gap_px = font.measure(COL_GAP)
        char_w = font.measure(" ")

        def col_w(n):
            return font.measure(" " * n)

        row_content_px = col_w(w_id) + gap_px + ICON_SIZE + gap_px + col_w(w_device) + gap_px + col_w(w_hostname) + gap_px + col_w(w_ip) + gap_px + col_w(3)

        w = self.text.winfo_width()
        if w > row_content_px:
            pad_chars = int((w - row_content_px) // 2 // char_w)
            center_pad = " " * max(0, pad_chars)
        else:
            center_pad = "  "

        center_px = font.measure(center_pad)
        tabs = []
        t = center_px + col_w(w_id) + gap_px
        tabs.append(t)
        t += ICON_SIZE + gap_px
        tabs.append(t)
        t += col_w(w_device) + gap_px
        tabs.append(t)
        t += col_w(w_hostname) + gap_px
        tabs.append(t)
        t += col_w(w_ip) + gap_px
        tabs.append(t)

        self.text.configure(tabs=tabs)

        scroll_pos = self.text.yview()[0]

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        for m in machines:
            self._insert_line(m, center_pad)

        self.text.yview_moveto(scroll_pos)
        self.text.configure(state=tk.DISABLED)

        self._poll_id = self.after(2000, self._poll)
