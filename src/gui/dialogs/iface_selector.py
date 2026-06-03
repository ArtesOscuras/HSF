import tkinter as tk
import netifaces


class InterfaceSelector(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None

        self.title("Select Interface")
        self.geometry("500x300")
        self.configure(bg="#111111")

        self.transient(parent)
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        tk.Label(
            self,
            text="Select a network interface for scanning:",
            font=("Menlo", 11),
            fg="#ffffff",
            bg="#111111",
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        list_frame = tk.Frame(self, bg="#000000")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_frame,
            bg="#000000",
            fg="#ffffff",
            selectbackground="#333333",
            selectforeground="#ffffff",
            font=("Menlo", 12),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        self._interfaces = self._list_interfaces()
        for name, ip, _ in self._interfaces:
            self.listbox.insert(tk.END, f"  {name:<8} {ip}")

        if self._interfaces:
            self.listbox.selection_set(0)

        btn_frame = tk.Frame(self, bg="#111111")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))

        cancel_btn = tk.Label(
            btn_frame,
            text="  Cancel  ",
            bg="#222222",
            fg="#ffffff",
            font=("Menlo", 10),
            relief=tk.RAISED,
            bd=1,
            padx=15,
            pady=6,
            cursor="hand2",
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
        cancel_btn.bind("<Button-1>", lambda e: self._cancel())
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg="#333333"))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg="#222222"))

        select_btn = tk.Label(
            btn_frame,
            text="  Select  ",
            bg="#222222",
            fg="#ffffff",
            font=("Menlo", 10),
            relief=tk.RAISED,
            bd=1,
            padx=15,
            pady=6,
            cursor="hand2",
        )
        select_btn.pack(side=tk.RIGHT)
        select_btn.bind("<Button-1>", lambda e: self._select())
        select_btn.bind("<Enter>", lambda e: select_btn.config(bg="#333333"))
        select_btn.bind("<Leave>", lambda e: select_btn.config(bg="#222222"))

        self.listbox.bind("<Return>", lambda e: self._select())
        self.listbox.bind("<Double-Button-1>", lambda e: self._select())
        self.listbox.focus_set()

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.wait_window(self)

    @staticmethod
    def _list_interfaces():
        result = []
        for iface in netifaces.interfaces():
            if iface == "lo0":
                continue
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET)
            if addrs:
                result.append((iface, addrs[0]["addr"], addrs[0]["netmask"]))
        return result

    def _select(self):
        sel = self.listbox.curselection()
        if sel:
            self.result = self._interfaces[sel[0]]
        self.destroy()

    def _cancel(self):
        self.destroy()
