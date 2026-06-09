import os
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from .base import BaseView
from src.machines import domain_db

MUTED = "#888888"
BRIGHT = "#ffffff"
INFO = "#5ba3ec"

ICON_SIZE = 32
COL_GAP = "   "

_icon = None


def _load_icon():
    global _icon
    if _icon is not None:
        return _icon
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "icons", "domain.png")
    path = os.path.abspath(path)
    if os.path.isfile(path):
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
            _icon = ImageTk.PhotoImage(img)
        except Exception:
            _icon = False
    else:
        _icon = False
    return _icon


class DomainListView(BaseView):
    name = "domains"
    description = "Discovered domains"

    MIN_DOMAIN = 10

    def _build_ui(self):
        _load_icon()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 5))

        tk.Label(
            header,
            text="Domains",
            font=("Menlo", 22, "bold"),
            fg="#ffffff",
            bg="#000000",
        ).pack(anchor="center")

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
        self.text.tag_configure("info", foreground=INFO)

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

    def _insert_line(self, domain, info, w_domain, center_pad):
        first = info.get("first_seen", "") if info else ""
        if first and "T" in first:
            first = first[:19].replace("T", " ")

        self.text.insert(tk.END, center_pad, "bright")

        icon = _load_icon()
        if icon:
            self.text.image_create(tk.END, image=icon)
        else:
            self.text.insert(tk.END, "?")
        self.text.insert(tk.END, COL_GAP, "bright")

        self.text.insert(tk.END, domain, "bright")
        self.text.insert(tk.END, " " * max(1, w_domain - len(domain)))
        self.text.insert(tk.END, COL_GAP, "bright")

        self.text.insert(tk.END, f"{first}\n", "muted")

    def _poll(self):
        domains = domain_db.list_all()
        domains.sort()

        w_domain = self.MIN_DOMAIN
        for d in domains:
            w_domain = max(w_domain, len(d))

        font = tkfont.Font(font=self.text.cget("font"))
        gap_px = font.measure(COL_GAP)

        row_content_px = (
            ICON_SIZE + gap_px
            + font.measure("M" * w_domain) + gap_px
            + font.measure("2000-01-01 00:00:00")
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

        if not domains:
            self.text.insert(tk.END, "\n", "bright")
            self.text.insert(tk.END, center_pad, "bright")
            self.text.insert(tk.END, "No domains discovered yet.\n", "muted")
        else:
            for d in domains:
                info = domain_db.load_domain_info(d)
                self._insert_line(d, info, w_domain, center_pad)

        self.text.configure(state=tk.DISABLED)

        self._poll_id = self.after(2000, self._poll)
