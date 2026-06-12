import tkinter as tk
from .base import BaseView
from src.machines import store
from src.machines import machine_db


MUTED = "#888888"
BRIGHT = "#ffffff"
INFO = "#5ba3ec"


class MachineDetailView(BaseView):
    name = "machine_detail"
    description = "Machine detail view"

    def __init__(self, parent, machine, **kwargs):
        self._machine = machine
        self._domain_rows = []
        super().__init__(parent, **kwargs)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#000000")
        header.grid(row=0, column=0, sticky="ew", pady=(15, 10))

        self._title_label = tk.Label(
            header,
            text="",
            font=("Menlo", 22, "bold"),
            fg="#ffffff",
            bg="#000000",
            cursor="hand2",
        )
        self._title_label.pack(anchor="center")
        self._title_label.bind("<Button-1>", self._on_title_click)
        self._on_back_click = None
        self._last_hash = None

        text_frame = tk.Frame(self, bg="#000000")
        text_frame.grid(row=1, column=0, sticky="nsew", padx=(220, 20), pady=(0, 20))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            bg="#000000",
            fg=BRIGHT,
            font=("Menlo", 13),
            borderwidth=0,
            highlightthickness=0,
            state=tk.DISABLED,
            wrap=tk.WORD,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        scrollbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                            width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("bright", foreground=BRIGHT)
        self.text.tag_configure("info", foreground=INFO)

        self._poll_id = None

    def on_activate(self):
        self.text.bind("<Button-1>", self._on_line_click)
        self.text.bind("<Motion>", self._on_mouse_move)
        self._poll()

    def on_deactivate(self):
        self.text.unbind("<Button-1>")
        self.text.unbind("<Motion>")
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _on_title_click(self, event):
        if self._on_back_click:
            self._on_back_click()

    def _on_line_click(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0])
        for row, domain in self._domain_rows:
            if line == row:
                if self._on_domain_click:
                    self._on_domain_click(domain)
                return "break"
        return "break"

    def _on_mouse_move(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0])
        cursor = ""
        for row, _ in self._domain_rows:
            if line == row:
                cursor = "hand2"
                break
        self.text.configure(cursor=cursor)

    def _poll(self):
        self._refresh()
        self._poll_id = self.after(2000, self._poll)

    def _refresh(self):
        m = store.get(self._machine.ip)
        if m:
            self._machine = m

        ports = machine_db.load_tcp_ports(self._machine.id)
        web = machine_db.load_web_services(self._machine.id)
        domains = machine_db.load_domains(self._machine.id)
        banners = machine_db.load_banners(self._machine.id)
        directories = machine_db.load_directories(self._machine.id)
        current_hash = hash((
            self._machine.device_type, self._machine.model, self._machine.os,
            self._machine.domain, self._machine.hostname, self._machine.mac,
            tuple(ports), tuple((p, o) for p, o in web), tuple(domains),
            tuple(banners), tuple(directories),
        ))
        if current_hash == self._last_hash and self.text.index("end-1c") != "1.0":
            return
        self._last_hash = current_hash

        try:
            first_line = self.text.index("@0,0")
            line_num = int(first_line.split(".")[0])
        except Exception:
            line_num = 1

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        m = self._machine

        self._title_label.config(text=f"Machine #{m.id} — {m.ip}")

        rows = [
            ("Hostname", m.hostname),
            ("MAC", m.mac),
            ("Type", m.device_type),
            ("Model", m.model),
            ("OS", m.os),
            ("Domain", m.domain),
            ("Methods", ", ".join(sorted(m.methods))),
            ("First seen", m.first_seen.strftime("%Y-%m-%d %H:%M:%S")),
            ("Last seen", m.last_seen.strftime("%Y-%m-%d %H:%M:%S")),
        ]
        label_w = max(len(r[0]) for r in rows) + 2
        for label, value in rows:
            self.text.insert(tk.END, f"  {label + ':':<{label_w}} ", "muted")
            self.text.insert(tk.END, f"{value or '-'}\n", "bright")

        domains = machine_db.load_domains(m.id)
        if domains:
            self._domain_rows = []
            self.text.insert(tk.END, f"\nDomains:\n", "info")
            for d, src in domains:
                row_start = int(self.text.index("end-1c").split(".")[0])
                self.text.insert(tk.END, f"  {d}", "bright")
                if src:
                    self.text.insert(tk.END, f" ({src})", "muted")
                self.text.insert(tk.END, "\n")
                self._domain_rows.append((row_start, d))
        else:
            self._domain_rows = []

        banners = machine_db.load_banners(m.id)
        if banners:
            last_port = None
            for p, out, probe in reversed(banners):
                if out.strip():
                    last_port = p
                    break
            if last_port is not None:
                for p, out, probe in banners:
                    if p == last_port and out.strip():
                        out_short = out.split("\n")[0][:100]
                        self.text.insert(tk.END, f"\nBanner port {p} ({probe}):\n", "info")
                        self.text.insert(tk.END, f"  {out_short}\n", "bright")
                        break

        ports = machine_db.load_tcp_ports(m.id)
        if ports:
            self.text.insert(tk.END, f"\nTCP ports ({len(ports)}):\n", "info")
            port_w = max(len(str(p)) for p in ports) + 2
            for p in ports:
                self.text.insert(tk.END, f"  {str(p):<{port_w}}", "muted")
                self.text.insert(tk.END, f"{_service_name(p)}\n", "bright")
        else:
            self.text.insert(tk.END, "\nTCP ports: (not scanned yet)\n", "muted")

        web = machine_db.load_web_services(m.id)
        if web:
            for port, output in web:
                self.text.insert(tk.END, f"\nWeb port {port}:\n", "info")
                for line in output.split("\n"):
                    self.text.insert(tk.END, f"  {line}\n", "bright")

        directories = machine_db.load_directories(m.id)
        if directories:
            self.text.insert(tk.END, f"\nDirectories ({len(directories)}):\n", "info")
            for path, ts in directories:
                self.text.insert(tk.END, f"  {path}\n", "bright")

        last_line = self.text.index("end-1c")
        total = int(last_line.split(".")[0]) if last_line else 1
        fraction = line_num / max(total, 1)
        self.text.yview_moveto(min(fraction, 1.0))
        self.text.configure(state=tk.DISABLED)


_SERVICES = {
    7: "echo", 9: "discard", 13: "daytime", 21: "ftp", 22: "ssh", 23: "telnet",
    25: "smtp", 37: "time", 49: "tacacs", 53: "dns", 69: "tftp", 70: "gopher",
    79: "finger", 80: "http", 88: "kerberos", 110: "pop3", 111: "rpcbind",
    113: "ident", 119: "nntp", 123: "ntp", 135: "msrpc", 137: "netbios-ns",
    138: "netbios-dgm", 139: "netbios-ssn", 143: "imap", 161: "snmp", 162: "snmptrap",
    179: "bgp", 199: "smux", 389: "ldap", 443: "https", 445: "smb", 465: "smtps",
    512: "exec", 513: "login", 514: "shell", 515: "printer", 548: "afp",
    554: "rtsp", 587: "submission", 631: "ipp", 636: "ldaps", 646: "ldp",
    873: "rsync", 993: "imaps", 995: "pop3s", 1025: "rpc", 1026: "rpc",
    1027: "rpc", 1080: "socks", 1099: "rmireg", 1433: "mssql", 1434: "mssql",
    1521: "oracle", 1723: "pptp", 2049: "nfs", 2121: "ftp-proxy",
    2222: "ssh-alt", 2375: "docker", 2701: "sms", 3128: "squid",
    3260: "iscsi", 3306: "mysql", 3389: "rdp", 3690: "svn", 4369: "epmd",
    4444: "krb524", 4786: "cisco", 4848: "appserv", 5000: "upnp",
    5353: "mdns", 5432: "postgres", 5555: "adb", 5672: "amqp",
    5800: "vnc", 5900: "vnc", 5985: "winrm", 5986: "winrm-ssl",
    6379: "redis", 6667: "irc", 7001: "weblogic", 7002: "weblogic",
    7777: "cbt", 8000: "http-alt", 8009: "ajp", 8080: "http-proxy",
    8180: "http-alt", 8443: "https-alt", 8888: "http-alt",
    9000: "cslistener", 9090: "websm", 9200: "elastic", 9443: "https-alt",
    9999: "abyss", 11211: "memcache", 27017: "mongodb", 50070: "hdfs",
    61616: "activemq",
}


def _service_name(port):
    return _SERVICES.get(port, "")
