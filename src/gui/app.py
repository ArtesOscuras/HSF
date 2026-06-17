import os
import platform
import re
import shutil
import socket
import subprocess
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
import netifaces
from . import fonts
from .console import Console
from .visualizer import Visualizer
from .views import NetworkView, DomainListView, EvidenceListView, CredentialListView, UserPassView, HashListView, ShellListView, ToolsView
from .dialogs import ScanDialog
from src import settings as hsf_settings
from src.machines import store, start_autosave as start_machines_autosave, stop_autosave as stop_machines_autosave
from src.machines import machine_db
from src.machines import domain_db
import src.machines
from src.tools.scanner import PassiveMDNSScanner, ActiveScanner
from src.tools.scanner.mdns_cache import load as load_mdns_cache, save as save_mdns_cache, start_autosave, clear as clear_mdns_cache, wipe as wipe_mdns_cache
from src.tools.scanner.identifier import identify_device, get_gateway_ip, extract_model_for_ip, _probe_smb_info, _probe_ssh_banner, _probe_ttl, _run_whatweb, _probe_web_internal, _identify_linux_distro, _extract_domains_from_whatweb, _dbg
from src.shells import ShellListener, shell_db
from src import event_bus


class _ReviewDialogManager:
    def __init__(self, parent):
        self._parent = parent
        self._dlg = None
        self._url_entry = None
        self._method_var = None
        self._headers_text = None
        self._resp_headers_text = None
        self._body_text = None
        self._status_label = None
        self._resp_header_label = None
        self._on_send = None
        self._done = None
        self._stage = None
        self._review_out = False
        self._review_in = False

    def add(self, url, method, headers, body, res_type, stage, on_send, done,
            resp_status=None, resp_status_text=None, resp_headers=None, resp_body=""):
        _dbg(f"[review] add: stage={stage} review_out={self._review_out} review_in={self._review_in} url={url[:80]}")
        if stage == "Request" and not self._review_out:
            _dbg("[review] continuing (outgoing off)")
            on_send()
            done.set()
            return
        if stage == "Response" and not self._review_in:
            _dbg("[review] continuing (incoming off)")
            on_send()
            done.set()
            return
        _dbg("[review] adding to pending")
        self._on_send = on_send
        self._done = done
        self._stage = stage
        self._pending = (url, method, headers, body, res_type,
                         resp_status, resp_status_text, resp_headers, resp_body)
        self._parent.after(0, self._show_pending)

    def show_waiting(self):
        self._parent.after(100, self._show_waiting_ui)

    def _show_pending(self):
        if self._dlg is None:
            self._build_dialog()
        url, method, headers, body, res_type, resp_status, resp_status_text, resp_headers, resp_body = self._pending
        label = "OUTGOING" if self._stage == "Request" else "INCOMING"
        self._dlg.title(f"Review Request — {label}")
        self._url_entry.delete(0, tk.END)
        self._url_entry.insert(0, url)
        self._method_var.set(method)
        info_parts = []
        if res_type:
            info_parts.append(f"Type: {res_type}")
            if self._stage == "Response" and res_type == "Document":
                info_parts.append("WARNING: body edits not supported for page HTML")
        if self._stage == "Response":
            info_parts.append(f"Status: {resp_status or '?'} {resp_status_text or ''}")
        self._status_label.configure(text="  |  ".join(info_parts) if info_parts else "")
        self._headers_text.configure(state=tk.NORMAL)
        self._headers_text.delete("1.0", tk.END)
        if headers:
            for k, v in headers.items():
                self._headers_text.insert(tk.END, f"{k}: {v}\n")
        self._headers_text.configure(state=tk.NORMAL)
        self._resp_headers_text.configure(state=tk.NORMAL)
        self._resp_headers_text.delete("1.0", tk.END)
        if self._stage == "Response" and resp_headers:
            for k, v in resp_headers.items():
                self._resp_headers_text.insert(tk.END, f"{k}: {v}\n")
        self._resp_headers_text.configure(state=tk.NORMAL)
        self._body_text.configure(state=tk.NORMAL)
        self._body_text.delete("1.0", tk.END)
        display = body if self._stage == "Request" and body else ""
        if self._stage == "Response" and resp_body:
            display = resp_body
        if display:
            self._body_text.insert("1.0", display)
        self._original_body = self._body_text.get("1.0", "end-1c")
        self._body_text.configure(state=tk.NORMAL)
        self._dlg.deiconify()
        self._dlg.lift()
        self._dlg.focus_set()

    def _build_dialog(self):
        self._dlg = tk.Toplevel(self._parent)
        self._dlg.title("Review Request")
        self._dlg.geometry("800x750")
        self._dlg.configure(bg="#111111")
        self._dlg.protocol("WM_DELETE_WINDOW", self._send_and_close)
        self._dlg.columnconfigure(0, weight=1)
        row = 0
        self._dlg.rowconfigure(row, weight=0)

        url_frame = tk.Frame(self._dlg, bg="#111111")
        url_frame.grid(row=row, column=0, sticky="ew", padx=15, pady=(10, 0))
        url_frame.columnconfigure(1, weight=1)
        tk.Label(url_frame, text="URL:", bg="#111111", fg="#aaaaaa",
                 font=("Menlo", 10)).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self._url_entry = tk.Entry(url_frame, bg="#000000", fg="#ffffff",
                                   font=("Menlo", 10), borderwidth=0, highlightthickness=1,
                                   highlightbackground="#333333", insertbackground="#ffffff")
        self._url_entry.grid(row=0, column=1, sticky="ew")
        row += 1
        self._dlg.rowconfigure(row, weight=0)

        info_frame = tk.Frame(self._dlg, bg="#111111")
        info_frame.grid(row=row, column=0, sticky="ew", padx=15, pady=(5, 0))
        info_frame.columnconfigure(2, weight=1)
        tk.Label(info_frame, text="Method:", bg="#111111", fg="#aaaaaa",
                 font=("Menlo", 10)).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self._method_var = tk.StringVar(value="GET")
        method_menu = tk.OptionMenu(info_frame, self._method_var, "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")
        method_menu.configure(bg="#000000", fg="#ffffff", borderwidth=0, highlightthickness=0,
                               font=("Menlo", 10), activebackground="#333333", activeforeground="#ffffff")
        method_menu["menu"].configure(bg="#000000", fg="#ffffff", font=("Menlo", 10))
        method_menu.grid(row=0, column=1, sticky="w")
        self._status_label = tk.Label(info_frame, text="", bg="#111111", fg="#888888",
                                       font=("Menlo", 10))
        self._status_label.grid(row=0, column=2, sticky="w", padx=(15, 0))
        row += 1
        self._dlg.rowconfigure(row, weight=0)

        tk.Label(self._dlg, text="Request Headers:", bg="#111111", fg="#aaaaaa",
                 font=("Menlo", 10, "bold"), anchor="w").grid(row=row, column=0, sticky="ew", padx=15, pady=(10, 0))
        row += 1
        self._dlg.rowconfigure(row, weight=1)

        self._headers_text = tk.Text(self._dlg, bg="#000000", fg="#ffffff",
                                      font=("Menlo", 10), borderwidth=0, highlightthickness=1,
                                      highlightbackground="#333333", insertbackground="#ffffff",
                                      wrap=tk.NONE, padx=8, pady=8, height=5)
        self._headers_text.grid(row=row, column=0, sticky="nsew", padx=15, pady=(2, 0))
        row += 1
        self._dlg.rowconfigure(row, weight=0)

        self._resp_header_label = tk.Label(self._dlg, text="Response Headers:", bg="#111111", fg="#aaaaaa",
                                            font=("Menlo", 10, "bold"), anchor="w")
        self._resp_header_label.grid(row=row, column=0, sticky="ew", padx=15, pady=(10, 0))
        row += 1
        self._dlg.rowconfigure(row, weight=1)

        self._resp_headers_text = tk.Text(self._dlg, bg="#000000", fg="#ffffff",
                                           font=("Menlo", 10), borderwidth=0, highlightthickness=1,
                                           highlightbackground="#333333", insertbackground="#ffffff",
                                           wrap=tk.NONE, padx=8, pady=8, height=4)
        self._resp_headers_text.grid(row=row, column=0, sticky="nsew", padx=15, pady=(2, 0))
        row += 1
        self._dlg.rowconfigure(row, weight=0)

        tk.Label(self._dlg, text="Body:", bg="#111111", fg="#aaaaaa",
                 font=("Menlo", 10, "bold"), anchor="w").grid(row=row, column=0, sticky="ew", padx=15, pady=(10, 0))
        row += 1
        self._dlg.rowconfigure(row, weight=2)

        self._body_text = tk.Text(self._dlg, bg="#000000", fg="#ffffff",
                                   font=("Menlo", 10), borderwidth=0, highlightthickness=1,
                                   highlightbackground="#333333", insertbackground="#ffffff",
                                   wrap=tk.WORD, padx=8, pady=8)
        self._body_text.grid(row=row, column=0, sticky="nsew", padx=15, pady=(2, 0))
        row += 1
        self._dlg.rowconfigure(row, weight=0)

        check_frame = tk.Frame(self._dlg, bg="#111111")
        check_frame.grid(row=row, column=0, sticky="w", padx=15, pady=(8, 0))
        self._out_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            check_frame, text="  Review outgoing", variable=self._out_var,
            bg="#111111", fg="#888888", selectcolor="#111111",
            font=("Menlo", 10),
            activebackground="#111111", activeforeground="#ffffff",
            command=self._on_check_change,
        ).pack(side=tk.LEFT, padx=(0, 15))
        self._in_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            check_frame, text="  Review incoming", variable=self._in_var,
            bg="#111111", fg="#888888", selectcolor="#111111",
            font=("Menlo", 10),
            activebackground="#111111", activeforeground="#ffffff",
            command=self._on_check_change,
        ).pack(side=tk.LEFT)
        row += 1
        self._dlg.rowconfigure(row, weight=0)

        btn_frame = tk.Frame(self._dlg, bg="#111111")
        btn_frame.grid(row=row, column=0, sticky="ew", padx=15, pady=(8, 12))
        send_btn = tk.Label(
            btn_frame, text="  Send  ", bg="#222222", fg="#ffffff",
            font=("Menlo", 10), relief=tk.RAISED, bd=1,
            padx=15, pady=6,
        )
        send_btn.pack(side=tk.RIGHT)
        send_btn.bind("<Button-1>", lambda e: self._send_and_close())
        send_btn.bind("<Enter>", lambda e: send_btn.config(bg="#333333"))
        send_btn.bind("<Leave>", lambda e: send_btn.config(bg="#222222"))

    def _show_waiting_ui(self):
        if self._dlg is None:
            self._build_dialog()
        self._dlg.title("Review Request")
        self._url_entry.delete(0, tk.END)
        self._method_var.set("GET")
        self._status_label.configure(text="Waiting for requests...")
        self._headers_text.configure(state=tk.NORMAL)
        self._headers_text.delete("1.0", tk.END)
        self._resp_headers_text.configure(state=tk.NORMAL)
        self._resp_headers_text.delete("1.0", tk.END)
        self._body_text.configure(state=tk.NORMAL)
        self._body_text.delete("1.0", tk.END)
        self._dlg.deiconify()
        self._dlg.lift()
        self._dlg.focus_set()

    def _on_check_change(self):
        self._review_out = self._out_var.get()
        self._review_in = self._in_var.get()

    def _parse_text_headers(self, text_widget):
        raw = text_widget.get("1.0", "end-1c")
        headers = {}
        for line in raw.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip()] = v.strip()
        return headers

    def _send_and_close(self):
        if self._on_send:
            url = self._url_entry.get().strip()
            method = self._method_var.get()
            body = self._body_text.get("1.0", "end-1c")
            if body == self._original_body:
                body = None
            if self._stage == "Response":
                headers = self._parse_text_headers(self._resp_headers_text)
            else:
                headers = self._parse_text_headers(self._headers_text)
            self._on_send(url=url if url else None,
                          method=method if method else None,
                          headers=headers if headers else None,
                          body=body)
        self._original_body = ""
        self._on_send = None
        self._url_entry.delete(0, tk.END)
        self._method_var.set("GET")
        self._status_label.configure(text="Sent. Waiting for next request...")
        self._headers_text.configure(state=tk.NORMAL)
        self._headers_text.delete("1.0", tk.END)
        self._resp_headers_text.configure(state=tk.NORMAL)
        self._resp_headers_text.delete("1.0", tk.END)
        self._body_text.configure(state=tk.NORMAL)
        self._body_text.delete("1.0", tk.END)
        if self._done:
            self._done.set()
            self._done = None

    def close(self):
        def _close_ui():
            if self._dlg:
                self._dlg.destroy()
                self._dlg = None
            if self._done:
                self._done.set()
        self._parent.after(0, _close_ui)


class App(tk.Tk):
    def __init__(self):
        fonts.register_before_tk()
        super().__init__()
        fonts.set_root(self)
        self.title("HSF - Hack Station Framework")
        self.minsize(800, 600)
        self.state("normal")

        fonts.init(self)
        self.configure(bg="#000000")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._pane = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#2d2d2d",
                                     sashwidth=5, sashrelief=tk.FLAT, borderwidth=0)
        self._pane.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.visualizer = Visualizer(self._pane)
        self._pane.add(self.visualizer, stretch="always")

        hsf_settings.load()
        console_font = hsf_settings.get("console_font_size", 11)
        self.console = Console(self._pane, initial_font_size=console_font)
        self._pane.add(self.console, stretch="always")

        self.after(300, self._set_initial_sash)

        self._passive_scanner = None
        self._active_scanner = None
        self._selected_interface = None
        self._identifying_ips = set()
        self._system_process = None
        self._recorder = None
        self._tcpscan_running = False
        self._tcpscan_process = None
        self._udpscan_running = False
        self._bannergrab_running = False
        self._shell_listener = None

        self._register_views()
        self.visualizer.activate_view("tools")
        self._register_commands()

        view_scale = hsf_settings.get("view_scale", 1.0)
        from src.gui.views.nav import set_initial_zoom as _nav_set_zoom
        _nav_set_zoom(view_scale)

        load_mdns_cache()
        start_autosave()
        store.load()
        start_machines_autosave(store)

        self.after(500, self._run_init_checks)

        event_bus.start(self, self._process_scanner_events)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _run_init_checks(self):
        from .dialogs.init_dialog import InitDialog
        dialog = InitDialog(self)
        self.wait_window(dialog)
        if self._passive_scanner is None or not self._passive_scanner.is_running:
            self._start_passive_scanner()
        if self._shell_listener is None or not self._shell_listener.is_running:
            self._start_shell_listener()

    def _set_initial_sash(self):
        self.update_idletasks()
        h = self.winfo_height()
        if h > 100:
            self._pane.sash_place(0, 0, h * 2 // 3)

    def _start_passive_scanner(self):
        from src.tools.scanner.mdns import _check_permission
        if not _check_permission():
            self.console.error("mDNS passive scanner: permission denied. Run as root or install with CAP_NET_RAW.")
            return
        self._passive_scanner = PassiveMDNSScanner(on_host_callback=self._on_host_discovered)
        self._passive_scanner.start()
        self.console.info("Passive listening mDNS started")

    def _start_shell_listener(self):
        port = 443 if self._is_root() else 8443
        self._shell_listener = ShellListener(
            port=port,
            on_new_session=self._on_shell_session,
        )
        self._shell_listener.start()
        self.console.info(f"Reverse shell listener started on port {port}")

    def _register_views(self):
        net_view = NetworkView(self.visualizer)
        net_view._on_machine_click = self._open_machine_view
        self.visualizer.register_view("machines", net_view)

        domain_view = DomainListView(self.visualizer)
        domain_view._on_domain_click = self._open_domain_view
        self.visualizer.register_view("domains", domain_view)

        evidence_view = EvidenceListView(self.visualizer)
        evidence_view._on_item_click = self._open_evidence_view
        self.visualizer.register_view("evidences", evidence_view)

        cred_view = CredentialListView(self.visualizer)
        cred_view._on_cred_click = self._open_credential_view
        self.visualizer.register_view("credentials", cred_view)

        user_pass_view = UserPassView(self.visualizer)
        def _log_cred(user, pwd):
            self.console.info(f"credentials {user} / {pwd} created")
        user_pass_view._on_cred_created = _log_cred
        self.visualizer.register_view("user-pass", user_pass_view)

        hash_view = HashListView(self.visualizer)
        hash_view._on_hash_click = self._open_hash_view
        self.visualizer.register_view("hashes", hash_view)

        tools_view = ToolsView(self.visualizer)
        tools_view._on_tool_click = self._on_tool_click
        self.visualizer.register_view("tools", tools_view)

        shell_view = ShellListView(self.visualizer)
        shell_view._on_shell_click = self._open_shell_view
        self.visualizer.register_view("shells", shell_view)

    def _register_commands(self):
        self.console.register_command("view", self._cmd_view, "Switch or list views")
        self.console.set_subcommands("view", ["list", "tools", "machines", "machine", "domains", "domain", "shells", "shell", "credentials", "credential", "hashes", "hash", "users", "passwords", "evidences", "evidence"])
        self.console.register_command("use", self._cmd_use, "Use a tool")
        self.console.set_subcommands("use", ["scanner", "bannergrab", "fuzzer", "webrecorder", "nslookup", "ping", "tcpscan", "udpscan", "whatweb", "ftp"])
        self.console.register_command("start", self._cmd_start, "Start listeners")
        self.console.set_subcommands("start", ["shells-listener", "mdns-listener"])
        self.console.register_command("stop", self._cmd_stop, "Stop listeners")
        self.console.set_subcommands("stop", ["shells-listener", "mdns-listener"])
        self.console.register_command("delete", self._cmd_delete, "Delete stored data")
        self.console.set_subcommands("delete", ["dbs", "credential", "evidence", "hash", "machine", "domain", "user", "password", "shell"])
        self.console.register_command("add", self._cmd_add, "Add to inventory")
        self.console.set_subcommands("add", ["machine", "domain", "credential", "user", "password", "hash"])
        self.console.register_command("init", self._cmd_init, "Re-run initialization checks")
        self.console.register_command("exit", self._cmd_exit, "Close the application")

        self.console.set_system_handler(self._run_system)
        self.console.set_system_stop_handler(self._stop_system)

    def _cmd_view(self, args):
        if not args:
            self.console.body("Usage: view <subcommand> or view list")
            return
        sub = args[0].lower()
        rest = args[1:]
        if sub == "list":
            names = self.visualizer.get_view_names()
            if names:
                self.console.title("Available views")
                for n in names:
                    v = self.visualizer.get_view(n)
                    desc = getattr(v, "description", "")
                    self.console.body(f"  {n:<12} {desc}")
            else:
                self.console.warning("No views available.")
        elif sub == "machine":
            self._cmd_view_machine(rest)
        elif sub == "domain":
            self._cmd_view_domain(rest)
        elif sub == "shell":
            self._cmd_view_shell(rest)
        elif sub == "credential":
            self._cmd_view_credential(rest)
        elif sub == "hash":
            self._cmd_view_hash(rest)
        elif sub == "evidence":
            self._cmd_view_evidence_name(rest)
        elif sub in ("tools", "machines", "domains", "shells", "credentials", "hashes", "users", "passwords", "evidences"):
            target = "user-pass" if sub in ("users", "passwords") else sub
            self.visualizer.activate_view(target)
        else:
            self.console.error(f"Unknown view subcommand: {sub}. Use 'view list' to see available views.")

    def _resolve_target(self, target):
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", target):
            return target, None
        if re.match(r"^\d+$", target):
            mid = int(target)
            for m in store.get_all():
                if m.id == mid:
                    return m.ip, m
        m = store.get(target)
        if m:
            return target, m
        for d in domain_db.list_all():
            if d == target:
                info = domain_db.load_domain_info(d)
                return target, None
        return None, None

    def _resolve_to_ip(self, target):
        ip, machine = self._resolve_target(target)
        if ip and re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
            return ip
        try:
            info = socket.getaddrinfo(target, None, socket.AF_INET, socket.SOCK_STREAM)
            if info:
                ip = info[0][4][0]
                dom = target
                machine = store.get(ip)
                if not machine:
                    machine = store.add_or_update(ip=ip, method="manual")
                    machine.device_type = "device unknown"
                    machine_db.save_machine_info(machine)
                if not domain_db.exists(dom):
                    domain_db.init_or_update(dom, machine.id, machine.ip, "use")
                self.console.info(f"{dom} -> {ip}")
                return ip
        except Exception:
            pass
        return None

    def _cmd_use(self, args):
        if not args:
            self.console.body("Usage: use <scanner|bannergrab|fuzzer|webrecorder|nslookup|ping|tcpscan|udpscan|whatweb|ftp> ...")
            return
        sub = args[0].lower()
        rest = args[1:]
        if sub == "scanner":
            self._cmd_use_scanner(rest)
        elif sub == "bannergrab":
            self._cmd_use_bannergrab(rest)
        elif sub == "fuzzer":
            self._cmd_use_fuzzer(rest)
        elif sub == "webrecorder":
            self._cmd_use_recorder(rest)
        elif sub == "nslookup":
            self._cmd_use_nslookup(rest)
        elif sub == "ping":
            self._cmd_use_ping(rest)
        elif sub == "tcpscan":
            self._cmd_use_tcpscan(rest)
        elif sub == "udpscan":
            self._cmd_use_udpscan(rest)
        elif sub == "whatweb":
            self._cmd_use_whatweb(rest)
        elif sub == "ftp":
            self._cmd_ftp(rest)
        else:
            self.console.error(f"Unknown tool: {sub}")

    def _cmd_use_scanner(self, args):
        if not args:
            self._scan_active()
            return
        ip = self._resolve_to_ip(args[0])
        if not ip:
            self.console.body("Usage: use scanner [<ip|id|domain>]")
            return
        self._scan_ip(ip)

    def _cmd_use_bannergrab(self, args):
        if not args:
            self._show_scan_dialog()
            return
        self._cmd_bannergrab(args)

    def _cmd_use_fuzzer(self, args):
        self._cmd_fuzz(args)

    def _cmd_use_recorder(self, args):
        self._cmd_recorder(args)

    def _cmd_use_nslookup(self, args):
        if not args:
            self.console.body("Usage: use nslookup <ip|id|domain>")
            return
        self._cmd_nslookup(args)

    def _cmd_use_ping(self, args):
        if not args:
            self.console.body("Usage: use ping <ip|id|domain>")
            return
        self._cmd_ping(args)

    def _cmd_use_tcpscan(self, args):
        self._cmd_tcpscan(args)

    def _cmd_use_udpscan(self, args):
        self._cmd_udpscan(args)

    def _cmd_use_whatweb(self, args):
        self._cmd_whatweb(args)

    def _cmd_view_machine(self, args):
        if not args:
            self.console.body("Usage: view machine <id|ip>")
            return
        target = args[0]
        machine = store.get(target)
        if not machine and target.isdigit():
            mid = int(target)
            for m in store.get_all():
                if m.id == mid:
                    machine = m
                    break
        if not machine:
            self.console.warning(f"No machine found for: {target}")
            return
        view_name = f"machine_{machine.id}"
        if view_name not in self.visualizer.get_view_names():
            from .views import MachineDetailView
            machine_view = MachineDetailView(self.visualizer, machine)
            machine_view._on_back_click = lambda: self.visualizer.activate_view("machines")
            machine_view._on_domain_click = self._open_domain_view
            self.visualizer.register_view(view_name, machine_view)
        self.visualizer.activate_view(view_name)

    def _cmd_view_domain(self, args):
        if not args:
            self.console.body("Usage: view domain <domain>")
            return
        domain = args[0]
        if not domain_db.exists(domain):
            try:
                info = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
                ip = info[0][4][0] if info else None
            except Exception:
                ip = None
            if ip:
                machine = store.get(ip)
                if not machine:
                    machine = store.add_or_update(ip=ip, method="manual")
                    machine.device_type = "device unknown"
                    machine_db.save_machine_info(machine)
                domain_db.init_or_update(domain, machine.id, machine.ip, "view")
            else:
                domain_db.init_or_update(domain, 0, "", "view")
        view_name = f"domain_{domain}"
        if view_name not in self.visualizer.get_view_names():
            from .views import DomainDetailView
            detail_view = DomainDetailView(self.visualizer, domain)
            detail_view._on_back_click = lambda: self.visualizer.activate_view("domains")
            detail_view._on_subdomain_click = self._open_domain_view
            detail_view._on_machine_click = self._open_machine_view_by_ip
            self.visualizer.register_view(view_name, detail_view)
        self.visualizer.activate_view(view_name)

    def _open_machine_view(self, machine):
        self._cmd_view_machine([str(machine.id)])

    def _open_machine_view_by_ip(self, ip):
        machine = store.get(ip)
        if machine:
            self._cmd_view_machine([str(machine.id)])
        else:
            self._cmd_view_machine([ip])

    def _cmd_view_shell(self, args):
        if not args:
            self.console.body("Usage: view shell <id|ip>")
            return
        target = args[0]
        session = None
        for s in shell_db.get_all():
            if s["ip"] == target:
                session = s
                break
        if not session and target.isdigit():
            session = shell_db.get_session(int(target))
        if not session:
            self.console.warning(f"No shell found for: {target}")
            return
        self._open_shell_view(session["id"])

    def _cmd_view_credential(self, args):
        if not args:
            self.console.body("Usage: view credential <username>")
            return
        from src.machines.credential_db import load_credentials
        username = args[0]
        for c in load_credentials():
            if c["username"] == username:
                self._open_credential_view(c["id"])
                return
        self.console.warning(f"No credential found for: {username}")

    def _cmd_view_hash(self, args):
        if not args:
            self.console.body("Usage: view hash <hash|id>")
            return
        from src.machines.credential_db import load_hashes
        target = args[0]
        for h in load_hashes():
            if h["hash"] == target:
                self._open_hash_view(h["id"])
                return
        if target.isdigit():
            self._open_hash_view(int(target))
            return
        self.console.warning(f"No hash found matching: {target}")

    def _cmd_view_evidence_name(self, args):
        if not args:
            self.console.body("Usage: view evidence <name>")
            return
        self._open_evidence_view(args[0])

    def _open_evidence_view(self, name):
        view_name = f"evidence_{name}"
        if view_name not in self.visualizer.get_view_names():
            from .views import EvidenceDetailView
            detail_view = EvidenceDetailView(self.visualizer, name)
            detail_view._on_back_click = lambda: self.visualizer.activate_view("evidences")
            self.visualizer.register_view(view_name, detail_view)
        self.visualizer.activate_view(view_name)

    def _open_credential_view(self, cred_id):
        view_name = f"credential_{cred_id}"
        if view_name not in self.visualizer.get_view_names():
            from .views import CredentialDetailView
            detail_view = CredentialDetailView(self.visualizer, cred_id)
            detail_view._on_back_click = lambda: self.visualizer.activate_view("credentials")
            self.visualizer.register_view(view_name, detail_view)
        self.visualizer.activate_view(view_name)

    def _open_hash_view(self, hash_id):
        view_name = f"hash_{hash_id}"
        if view_name not in self.visualizer.get_view_names():
            from .views import HashDetailView
            detail_view = HashDetailView(self.visualizer, hash_id)
            detail_view._on_back_click = lambda: self.visualizer.activate_view("hashes")
            self.visualizer.register_view(view_name, detail_view)
        self.visualizer.activate_view(view_name)

    def _on_tool_click(self, action):
        if action == "scanner":
            self._scan_active()
            if self._active_scanner and self._active_scanner.is_running:
                self.visualizer.activate_view("machines")
        elif action == "fuzzer":
            self._cmd_fuzz([])
        elif action == "webrecorder":
            self._cmd_recorder([])

    def _open_domain_view(self, domain):
        self._cmd_view_domain([domain])

    def _open_shell_view(self, sid):
        view_name = f"shell_{sid}"
        if view_name not in self.visualizer.get_view_names():
            from .views import ShellDetailView, SSHDetailView, ReverseShellDetailView
            s = shell_db.get_session(sid)
            stype = (s or {}).get("type", "")
            if stype == "SSH":
                detail_view = SSHDetailView(self.visualizer, sid)
            elif stype.startswith("Revershell"):
                detail_view = ReverseShellDetailView(self.visualizer, sid)
            else:
                detail_view = ShellDetailView(self.visualizer, sid)
            detail_view._on_back_click = lambda: self.visualizer.activate_view("shells")
            self.visualizer.register_view(view_name, detail_view)
        self.visualizer.activate_view(view_name)

    def _cmd_start_listener(self, args):
        if self._shell_listener and self._shell_listener.is_running:
            if args:
                self.console.warning(f"Shell listener already running on port {self._shell_listener.port}. Use stop-listener first.")
            else:
                self.console.warning(f"Shell listener already running on port {self._shell_listener.port}")
            return
        if args:
            try:
                port = int(args[0])
            except ValueError:
                self.console.error("Invalid port")
                return
            self._shell_listener = ShellListener(
                port=port,
                on_new_session=self._on_shell_session,
            )
            self._shell_listener.start()
            self.console.info(f"Reverse shell listener started on port {port}")
        else:
            self._start_shell_listener()

    def _cmd_start(self, args):
        if not args:
            self.console.body("Usage: start <shells-listener|mdns-listener>")
            return
        sub = args[0].lower()
        if sub == "shells-listener":
            self._cmd_start_shells(args[1:])
        elif sub == "mdns-listener":
            self._cmd_start_mdns(args[1:])
        else:
            self.console.error(f"Unknown start target: {sub}")

    def _cmd_start_shells(self, args):
        if self._shell_listener and self._shell_listener.is_running:
            self.console.warning(f"Shell listener already running on port {self._shell_listener.port}")
            return
        if args:
            try:
                port = int(args[0])
                if port < 1 or port > 65535:
                    self.console.error("Port must be between 1 and 65535")
                    return
            except ValueError:
                self.console.body("Usage: start shells-listener [port]")
                return
            self._shell_listener = ShellListener(port=port, on_new_session=self._on_shell_session)
            self._shell_listener.start()
            self.console.info(f"Reverse shell listener started on port {port}")
        else:
            self._start_shell_listener()

    def _cmd_start_mdns(self, args):
        if self._passive_scanner and self._passive_scanner.is_running:
            self.console.warning("Passive mDNS scanner is already running")
            return
        from src.tools.scanner.mdns import _check_permission
        if not _check_permission():
            self.console.error("mDNS passive scanner: permission denied. Run as root or install with CAP_NET_RAW.")
            return
        self._passive_scanner = PassiveMDNSScanner(on_host_callback=self._on_host_discovered)
        self._passive_scanner.start()
        self.console.info("Passive listening mDNS started")

    def _cmd_stop_listener(self, args):
        if self._shell_listener and self._shell_listener.is_running:
            self._shell_listener.stop()
            self._shell_listener = None
            self.console.info("Reverse shell listener stopped")
        else:
            self.console.warning("No shell listener is running")

    def _cmd_stop(self, args):
        if not args:
            self.console.body("Usage: stop <shells-listener|mdns-listener>")
            return
        sub = args[0].lower()
        if sub == "shells-listener":
            if self._shell_listener and self._shell_listener.is_running:
                self._shell_listener.stop()
                self._shell_listener = None
                self.console.info("Reverse shell listener stopped")
            else:
                self.console.warning("No shell listener is running")
        elif sub == "mdns-listener":
            if self._passive_scanner and self._passive_scanner.is_running:
                self._passive_scanner.stop()
                self._passive_scanner = None
                self.console.info("Passive mDNS scanner stopped")
            else:
                self.console.warning("Passive mDNS scanner is not running")
        else:
            self.console.error(f"Unknown stop target: {sub}")

    def _on_shell_session(self, **kwargs):
        if "error" in kwargs:
            self.console.after(0, lambda: self.console.error(f"Shell listener error: {kwargs['error']}"))
            return
        session = kwargs.get("session")
        if session:
            self.console.after(0, lambda s=session: self.console.success(
                f"New shell #{s['id']} from {s['ip']}:{s['source_port']}"
            ))

    def _cmd_scan(self, args):
        if not args:
            self._scan_active()
            return
        sub = args[0].lower()
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", sub):
            self._scan_ip(sub)
        elif sub == "active":
            self._scan_active()
        elif sub == "passive":
            self._scan_passive()
        elif sub == "iface":
            self._scan_iface(args[1:])
        elif sub == "stop":
            self._scan_stop()
        elif sub == "list":
            self._scan_list()
        else:
            self._show_scan_help()

    def _show_scan_help(self):
        iface_status = f" ({self._selected_interface[0]})" if self._selected_interface else " (none)"
        self.console.title("Scan commands")
        self.console.body(f"  scan [active]        ARP + mDNS + Nmap (all methods)")
        self.console.body(f"  scan <ip>            Identify a specific IP address")
        self.console.body(f"  scan passive         Restart passive mDNS discovery")
        self.console.body(f"  scan iface           List available interfaces")
        self.console.body(f"  scan iface <name>    Select interface by name")
        self.console.body(f"  scan stop            Stop active scan")
        self.console.body(f"  scan list            List discovered machines")
        self.console.body(f"  Interface{iface_status}")

    def _scan_iface(self, args):
        if args:
            name = args[0]
            addrs = netifaces.ifaddresses(name).get(netifaces.AF_INET)
            if addrs:
                self._selected_interface = (name, addrs[0]["addr"], addrs[0]["netmask"])
                src.machines.interface_name = name
                src.machines.interface_ip = addrs[0]["addr"]
                self.console.success(f"Interface set to {name} ({addrs[0]['addr']})")
            else:
                self.console.error(f"Interface '{name}' not found or has no IPv4")
            return

        self.console.title("Available interfaces")
        for iface in netifaces.interfaces():
            if iface == "lo0":
                continue
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET)
            if addrs:
                marker = " <--" if self._selected_interface and self._selected_interface[0] == iface else ""
                self.console.body(f"  {iface:<8} {addrs[0]['addr']:<18}{marker}")

    def _scan_passive(self):
        if self._passive_scanner and self._passive_scanner.is_running:
            self.console.warning("Passive scan is already running.")
            return
        from src.tools.scanner.mdns import _check_permission
        if not _check_permission():
            self.console.error("mDNS passive scanner: permission denied.")
            return
        self._passive_scanner = PassiveMDNSScanner(on_host_callback=self._on_host_discovered)
        self._passive_scanner.start()
        self.console.info("Passive listening mDNS started")

    def _scan_active(self):
        result = self._show_scan_dialog()
        if not result:
            self.console.warning("Scan cancelled")
            return

        action = result.get("action")
        ip = result.get("ip")

        if action == "scan":
            if ip:
                self._scan_ip(ip)
                return
            iface = result.get("iface")
            if not iface:
                return

            if self._active_scanner and self._active_scanner.is_running:
                self.console.warning("Active scan is already running.")
                return

            self._selected_interface = iface
            src.machines.interface_name = iface[0]
            src.machines.interface_ip = iface[1]
            iface_name = iface[0]
            try:
                self._active_scanner = ActiveScanner(
                    on_host_callback=self._on_host_discovered,
                    interface_name=iface_name,
                )
                self._active_scanner.start()
                self.console.info("Active scan started")
                nmap_status = "enabled" if self._active_scanner.has_nmap else "disabled"
                self.console.body(
                    f"    Interface: {self._active_scanner.interface_name}  "
                    f"Network: {self._active_scanner.network_cidr}  "
                    f"Nmap: {nmap_status}"
                )
                if not self._active_scanner.has_nmap:
                    self.console.info("nmap binary not available — ARP scanner using native mode")
            except RuntimeError as e:
                self.console.error(str(e))

        elif action == "tcpscan":
            self._cmd_tcpscan([ip])
        elif action == "udpscan":
            self._cmd_udpscan([ip])
        elif action == "bannergrab":
            self._cmd_bannergrab([ip, str(result.get("port", 80))])

    def _show_scan_dialog(self):
        dialog = ScanDialog(self)
        return dialog.result

    def _scan_stop(self):
        if self._active_scanner and self._active_scanner.is_running:
            self._active_scanner.stop()
            self._active_scanner = None
            self.console.info("Active scan stopped")
        else:
            self.console.warning("No active scan is running.")

    def _scan_ip(self, ip):
        self.console.info(f"Checking {ip}...")
        threading.Thread(target=self._run_scan_ip, args=(ip,), daemon=True).start()

    def _run_scan_ip(self, ip):
        src.machines.interface_name = ""
        src.machines.interface_ip = ""
        _dbg(f"[scan-ip] checking {ip} for evidence...")
        gateway = get_gateway_ip()
        result = identify_device(ip, gateway_ip=gateway, hostname="")
        ttl = _probe_ttl(ip)
        from src.tools.scanner.mdns_cache import get_services
        mds = get_services(ip)
        has_evidence = result != "device unknown" or ttl is not None or bool(mds)
        _dbg(f"[scan-ip] result={result} ttl={ttl} mds={sorted(mds.keys()) if mds else []} evidence={has_evidence}")
        if not has_evidence:
            event_bus.submit({"type": "scan_error", "message": f"No device detected at {ip}"})
            return
        machine = store.add_or_update(ip=ip, method="manual")
        machine.device_type = result
        model = extract_model_for_ip(machine.ip, resolve=True)
        if model:
            machine.model = model
        if result == "Windows machine":
            os_info, domain, server_name = _probe_smb_info(machine.ip)
            if os_info:
                machine.device_type = os_info
                machine.os = os_info
            if domain:
                machine.domain = domain
                domain_db.init_or_update(domain, machine.id, machine.ip, "smb")
                machine_db.save_domain(machine.id, domain, "smb")
            if server_name:
                machine.hostname = server_name
        if result == "Linux device":
            banner = _probe_ssh_banner(machine.ip)
            if banner:
                distro = _identify_linux_distro(banner)
                if distro:
                    machine.device_type = distro
                    machine.os = distro
        machine_db.save_machine_info(machine)
        event_bus.submit({"type": "scan_ip_result", "machine": machine})

    TCP_PORTS_COMMON = [
        7, 9, 13, 21, 22, 23, 25, 37, 49, 53, 69, 70, 79, 80, 88, 110, 111,
        113, 119, 123, 135, 137, 138, 139, 143, 161, 162, 179, 199, 389, 443,
        445, 465, 512, 513, 514, 515, 548, 554, 587, 631, 636, 646, 873, 993,
        995, 1025, 1026, 1027, 1080, 1099, 1433, 1434, 1521, 1723, 2049, 2121,
        2222, 2375, 2701, 3128, 3260, 3306, 3389, 3690, 4369, 4444, 4786, 4848,
        5000, 5353, 5432, 5555, 5672, 5800, 5900, 5985, 5986, 6379, 6667, 7001,
        7002, 7777, 8000, 8009, 8080, 8180, 8443, 8888, 9000, 9090, 9200, 9443,
        9999, 11211, 27017, 50070, 61616,
    ]

    @staticmethod
    def _is_root():
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False

    def _tcp_scan_connect(self, ip, ports, port_callback=None):
        open_ports = []
        def _check(p):
            if not self._tcpscan_running:
                return
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            try:
                if sock.connect_ex((ip, p)) == 0:
                    open_ports.append(p)
                    if port_callback:
                        port_callback(p)
            finally:
                sock.close()
        with ThreadPoolExecutor(max_workers=100) as exe:
            futures = [exe.submit(_check, p) for p in ports]
            for f in as_completed(futures):
                if not self._tcpscan_running:
                    break
        return sorted(open_ports)

    def _tcp_scan_syn_nmap(self, ip, ports):
        port_list = ",".join(str(p) for p in ports)
        _dbg(f"[tcpscan-nmap] {ip} ports={len(ports)}")
        try:
            self._tcpscan_process = subprocess.Popen(
                ["nmap", "-n", "-Pn", "-sS", "-p", port_list, ip],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            )
            out, _ = self._tcpscan_process.communicate(timeout=120)
            _dbg(f"[tcpscan-nmap] output:\n{out}")
        except (subprocess.TimeoutExpired, Exception) as e:
            self._tcpscan_process.kill()
            self._tcpscan_process.communicate()
            _dbg(f"[tcpscan-nmap] killed: {e}")
            return []
        finally:
            self._tcpscan_process = None
        open_ports = []
        for line in out.splitlines():
            m = re.match(r"(\d+)/tcp\s+open", line)
            if m:
                open_ports.append(int(m.group(1)))
        _dbg(f"[tcpscan-nmap] done: open={len(open_ports)} ports={sorted(open_ports)}")
        return sorted(open_ports)

    @staticmethod
    def _detect_scan_method():
        if shutil.which("nmap"):
            return "SYN"
        return "connect"

    def _tcp_scan(self, ip, ports, method, port_callback=None):
        if method.startswith("SYN"):
            return self._tcp_scan_syn_nmap(ip, ports)
        return self._tcp_scan_connect(ip, ports, port_callback=port_callback)

    def _run_tcpscan(self, ip, method):
        machine = store.get(ip)
        self._tcpscan_running = True
        all_ports = []
        try:
            def _save_ports():
                if machine and machine.id:
                    machine_db.save_tcp_ports(machine.id, sorted(all_ports))

            def _on_port(p):
                if p not in all_ports:
                    all_ports.append(p)
                _save_ports()

            # Phase 1: common ports
            open_ports = self._tcp_scan(ip, self.TCP_PORTS_COMMON, method, port_callback=_on_port)
            for p in open_ports:
                if p not in all_ports:
                    all_ports.append(p)
            _save_ports()
            for p in open_ports:
                self.console.after(0, lambda port=p: self.console.success(
                    f"  {ip}  port {port} open"
                ))
            self.console.after(0, lambda: self.console.info(
                f"TCP common ports ({len(self.TCP_PORTS_COMMON)}) done. Continuing full scan (65535)..."
            ))

            if not self._tcpscan_running:
                self.console.after(0, lambda: self.console.warning(f"TCP scan {ip} stopped"))
                return

            # Phase 2: remaining ports
            common_set = set(self.TCP_PORTS_COMMON)
            remaining = [p for p in range(1, 65536) if p not in common_set]
            more = self._tcp_scan(ip, remaining, method, port_callback=_on_port)
            for p in more:
                if p not in all_ports:
                    all_ports.append(p)
            _save_ports()
            for p in more:
                self.console.after(0, lambda port=p: self.console.success(
                    f"  {ip}  port {port} open"
                ))
            self.console.after(0, lambda: self.console.info(
                f"TCP scan {ip} finished ({65535} ports): {len(all_ports)} open"
            ))
        finally:
            self._tcpscan_running = False

    def _get_active_machine(self):
        name = self.visualizer.get_active_view_name()
        if name and name.startswith("machine_"):
            try:
                mid = int(name.split("_")[1])
                for m in store.get_all():
                    if m.id == mid:
                        return m
            except (ValueError, IndexError):
                pass
        return None

    def _cmd_tcpscan(self, args):
        if not args:
            m = self._get_active_machine()
            if m:
                args = [str(m.id)]
            else:
                self.console.body("Usage: tcpscan <ip|id> | tcpscan stop")
                return
        sub = args[0].lower()
        if sub == "stop":
            if not self._tcpscan_running:
                self.console.warning("No tcpscan is running.")
                return
            self._tcpscan_running = False
            if self._tcpscan_process:
                self._tcpscan_process.kill()
            self.console.info("TCP scan stop requested")
            return
        ip = sub
        if re.match(r"^\d+$", ip):
            machine_id = int(ip)
            machine = None
            for m in store.get_all():
                if m.id == machine_id:
                    machine = m
                    break
            if machine:
                ip = machine.ip
            else:
                self.console.warning(f"No machine with ID #{machine_id}")
                return
        if self._tcpscan_running:
            self.console.warning("A TCP scan is already running.")
            return
        if self._udpscan_running:
            self._udpscan_running = False
            self.console.info("UDP scan stopped")
        _dbg(f"[tcpscan] requested for {ip}")
        if self._active_scanner and self._active_scanner.is_running:
            self._active_scanner.stop()
            self._active_scanner = None
            self.console.info("Active scan stopped")
        if self._is_root() and self._detect_scan_method() == "SYN":
            method = "SYN (nmap)"
        else:
            method = "connect" + (" (no root)" if not self._is_root() else "")
        self.console.info(f"TCP scanning {ip}  ({method})...")
        threading.Thread(target=self._run_tcpscan, args=(ip, method), daemon=True).start()

    UDP_PORTS_COMMON = [
        7, 9, 11, 13, 17, 19, 37, 42, 49, 53,
        67, 68, 69, 80, 88, 111, 113, 119, 123, 135,
        136, 137, 138, 139, 143, 158, 161, 162, 177, 194,
        201, 209, 213, 218, 220, 259, 264, 318, 323, 383,
        389, 401, 427, 443, 445, 464, 465, 497, 500, 512,
        513, 514, 515, 517, 518, 520, 521, 525, 529, 531,
        532, 533, 534, 540, 546, 547, 554, 563, 587, 591,
        593, 604, 623, 631, 636, 639, 646, 647, 648, 651,
        660, 666, 674, 691, 700, 702, 706, 711, 712, 720,
        749, 750, 751, 752, 753, 754, 758, 760, 782, 829,
        847, 848, 853, 859, 860, 861, 862, 873, 953, 989,
        990, 991, 992, 993, 995, 1001, 1062, 1194, 1434, 1521,
        1645, 1646, 1701, 1718, 1719, 1720, 1723, 1812, 1813, 1900,
        1901, 2000, 2049, 2082, 2083, 2222, 2223, 2427, 2727, 2967,
        3000, 3031, 3050, 3128, 3130, 3283, 3306, 3389, 3455, 3478,
        3632, 3689, 4000, 4001, 4063, 4105, 4369, 4444, 4500, 4569,
        4662, 4672, 4949, 5000, 5001, 5004, 5005, 5030, 5050, 5060,
        5080, 5093, 5190, 5222, 5223, 5269, 5298, 5351, 5353, 5355,
        5405, 5432, 5480, 5500, 5510, 5550, 5555, 5631, 5632, 5672,
        5683, 5713, 5721, 5722, 5746, 5800, 5863, 5900, 5984, 5985,
        6000, 6001, 6070, 6086, 6129, 6257, 6346, 6347, 6379, 6502,
        6544, 6665, 6666, 6667, 6668, 6669, 6881, 6900, 6980, 7000,
        7070, 7100, 7170, 7676, 7777, 7937, 8000, 8002, 8010, 8074,
        8080, 8081, 8086, 8087, 8200, 8443, 8765, 8888, 9000, 9001,
        9030, 9090, 9100, 9101, 9102, 9103, 9119, 9160, 9200, 9306,
        9312, 9418, 9443, 9535, 9536, 9875, 9898, 9981, 10000, 10080,
        11371, 12345, 13720, 13721, 14567, 15104, 17007, 19283, 19813, 20000,
        20720, 21000, 21554, 22273, 23073, 23399, 23456, 25565, 27000, 27017,
        27374, 28119, 31337, 33434, 34861, 37777, 40193, 41524, 45678, 49152,
        49153, 49167, 50000, 55553, 55555, 62078,
    ]

    def _udp_scan_connect(self, ip, ports, port_callback=None):
        open_ports = []
        def _check(p):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.5)
            try:
                sock.sendto(b"", (ip, p))
                sock.recvfrom(1024)
                open_ports.append(p)
                if port_callback:
                    port_callback(p)
            except socket.timeout:
                pass
            except (ConnectionRefusedError, OSError):
                pass
            finally:
                sock.close()
        with ThreadPoolExecutor(max_workers=100) as exe:
            futures = [exe.submit(_check, p) for p in ports]
            for f in as_completed(futures):
                if not self._udpscan_running:
                    break
        return sorted(open_ports)

    def _udp_scapy_probe(self, ip, ports):
        from scapy.all import IP, UDP, ICMP, sr1, RandShort
        open_ports = []
        for p in ports:
            if not self._udpscan_running:
                break
            try:
                pkt = IP(dst=ip) / UDP(sport=RandShort(), dport=p)
                reply = sr1(pkt, timeout=1.5, verbose=0)
                if reply is None:
                    open_ports.append(p)
                elif reply.haslayer(ICMP) and reply[ICMP].type == 3 and reply[ICMP].code == 3:
                    pass
                else:
                    open_ports.append(p)
            except Exception:
                pass
        return sorted(open_ports)

    def _udp_scan(self, ip, ports, port_callback=None):
        if self._is_root():
            return self._udp_scapy_probe(ip, ports)
        return self._udp_scan_connect(ip, ports, port_callback=port_callback)

    def _run_udpscan(self, ip):
        machine = store.get(ip)
        self._udpscan_running = True
        all_ports = []
        try:
            def _save_ports():
                if machine and machine.id:
                    machine_db.save_udp_ports(machine.id, sorted(all_ports))

            def _on_port(p):
                if p not in all_ports:
                    all_ports.append(p)
                _save_ports()

            method = "scapy" if self._is_root() else "connect"
            self.console.after(0, lambda: self.console.info(
                f"UDP scanning {ip} ({method})..."
            ))

            open_ports = self._udp_scan(ip, self.UDP_PORTS_COMMON, port_callback=_on_port)
            for p in open_ports:
                if p not in all_ports:
                    all_ports.append(p)
            _save_ports()
            for p in open_ports:
                self.console.after(0, lambda port=p: self.console.success(
                    f"  {ip}  UDP {port} open"
                ))

            if not self._udpscan_running:
                self.console.after(0, lambda: self.console.warning(f"UDP scan {ip} stopped"))
                return

            self.console.after(0, lambda: self.console.info(
                f"UDP common ports ({len(self.UDP_PORTS_COMMON)}) done. Continuing full scan (65535)..."
            ))

            common_set = set(self.UDP_PORTS_COMMON)
            remaining = [p for p in range(1, 65536) if p not in common_set]
            more = self._udp_scan(ip, remaining, port_callback=_on_port)
            for p in more:
                if p not in all_ports:
                    all_ports.append(p)
            _save_ports()
            for p in more:
                self.console.after(0, lambda port=p: self.console.success(
                    f"  {ip}  UDP {port} open"
                ))
            self.console.after(0, lambda: self.console.info(
                f"UDP scan {ip} finished ({65535} ports): {len(all_ports)} open"
            ))
        finally:
            self._udpscan_running = False

    def _cmd_udpscan(self, args):
        if not args:
            m = self._get_active_machine()
            if m:
                args = [str(m.id)]
            else:
                self.console.body("Usage: udpscan <ip|id> | udpscan stop")
                return
        sub = args[0].lower()
        if sub == "stop":
            if not self._udpscan_running:
                self.console.warning("No UDP scan is running.")
                return
            self._udpscan_running = False
            self.console.info("UDP scan stop requested")
            return
        ip = sub
        if re.match(r"^\d+$", ip):
            machine_id = int(ip)
            machine = None
            for m in store.get_all():
                if m.id == machine_id:
                    machine = m
                    break
            if machine:
                ip = machine.ip
            else:
                self.console.warning(f"No machine with ID #{machine_id}")
                return
        if self._udpscan_running:
            self.console.warning("A UDP scan is already running.")
            return
        if self._tcpscan_running:
            self._tcpscan_running = False
            if self._tcpscan_process:
                self._tcpscan_process.kill()
            self.console.info("TCP scan stopped")
        _dbg(f"[udpscan] requested for {ip}")
        threading.Thread(target=self._run_udpscan, args=(ip,), daemon=True).start()

    def _cmd_whatweb(self, args):
        m = self._get_active_machine()
        if not args:
            if m:
                args = [str(m.id)]
            else:
                self.console.body("Usage: whatweb <ip|id|domain> [port]")
                return
        target = args[0]
        port = 80
        if len(args) >= 2:
            try:
                port = int(args[1])
            except ValueError:
                self.console.error("Invalid port number")
                return
        machine = None
        domain_name = None
        if re.match(r"^\d+$", target):
            mid = int(target)
            for m in store.get_all():
                if m.id == mid:
                    machine = m
                    break
        elif re.match(r"^\d+\.\d+\.\d+\.\d+$", target):
            machine = store.get(target)
            if not machine:
                machine = store.add_or_update(ip=target, method="manual")
                machine.device_type = "device unknown"
                machine_db.save_machine_info(machine)
        else:
            if not domain_db.exists(target):
                domain_db.init_or_update(target, 0, "0.0.0.0", "manual")
            domain_name = target
            try:
                info = socket.getaddrinfo(domain_name, None, socket.AF_INET, socket.SOCK_STREAM)
                ip = info[0][4][0] if info else domain_name
            except Exception:
                ip = domain_name
            machine = store.get(ip)
            if not machine:
                machine = store.add_or_update(ip=ip, method="manual")
                machine.device_type = "device unknown"
                machine_db.save_machine_info(machine)
            domain_db.init_or_update(domain_name, machine.id, machine.ip, "whatweb")

        if not machine:
            self.console.warning(f"No machine found for: {target}")
            return
        ip = machine.ip
        threading.Thread(target=self._run_webscan, args=(ip, port, machine, domain_name), daemon=True).start()

    @staticmethod
    def _has_whatweb():
        try:
            r = subprocess.run(["whatweb", "--version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return True, "direct"
        except (FileNotFoundError, PermissionError, OSError, subprocess.TimeoutExpired):
            pass
        try:
            r = subprocess.run("whatweb --version", shell=True, capture_output=True, timeout=5)
            if r.returncode == 0:
                return True, "subshell"
        except (FileNotFoundError, PermissionError, OSError, subprocess.TimeoutExpired):
            pass
        try:
            shell = os.environ.get("SHELL", "/bin/sh")
            r = subprocess.run([shell, "-ic", "whatweb --version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                alias_r = subprocess.run(
                    [shell, "-ic", "alias whatweb 2>/dev/null"],
                    capture_output=True, timeout=5, text=True,
                )
                alias_out = alias_r.stdout.strip()
                if "whatweb=" in alias_out:
                    path = alias_out.split("whatweb=", 1)[1].strip().strip("'").strip('"')
                    if os.path.isfile(path):
                        return True, path
                return True, "interactive"
        except (FileNotFoundError, PermissionError, OSError, subprocess.TimeoutExpired):
            pass
        return False, ""

    @staticmethod
    def _strip_ansi(text):
        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def _run_webscan(self, ip, port, machine, domain_name=None):
        target = domain_name or ip
        found, mode = self._has_whatweb()
        if found:
            self.console.after(0, lambda: self.console.info(
                f"Web scanning {target}:{port} (whatweb)..."
            ))
            stdout, stderr = _run_whatweb(target, port, mode=mode)
            stdout = self._strip_ansi(stdout)
            stderr = self._strip_ansi(stderr)
            if stderr:
                for line in stderr.split("\n"):
                    if line.strip():
                        self.console.after(0, lambda l=line: self.console.error(f"  whatweb: {l}"))
                stdout = stdout + "\n" + stderr if stdout else stderr
            if stdout:
                machine_db.save_web_service(machine.id, port, stdout)
                if domain_name:
                    domain_db.save_web_service(domain_name, port, stdout)
                domains = _extract_domains_from_whatweb(stdout)
                for d in domains:
                    domain_db.init_or_update(d, machine.id, machine.ip, "whatweb")
                    machine_db.save_domain(machine.id, d, "whatweb")
                self.console.after(0, lambda: self.console.info(
                    f"Web scan {target}:{port} done (whatweb)"
                ))
                for d in domains:
                    self.console.after(0, lambda dom=d: self.console.success(f"  domain: {dom}"))
            else:
                self.console.after(0, lambda: self.console.warning(
                    f"No web service detected at {target}:{port}"
                ))
        else:
            self.console.after(0, lambda: self.console.error(
                "whatweb not found in path"
            ))
            self.console.after(0, lambda: self.console.info(
                f"Web scanning {target}:{port} (internal scanner)..."
            ))
            output = _probe_web_internal(target, port)
            engine = "internal"
            if output:
                machine_db.save_web_service(machine.id, port, output)
                if domain_name:
                    domain_db.save_web_service(domain_name, port, output)
                self.console.after(0, lambda: self.console.info(
                    f"Web scan {ip}:{port} done ({engine})"
                ))
                for line in output.split("\n"):
                    self.console.after(0, lambda l=line: self.console.body(f"  {l}"))
            else:
                self.console.after(0, lambda: self.console.warning(
                    f"No web service detected at {ip}:{port}"
                ))

    def _cmd_bannergrab(self, args):
        if not args:
            self.console.body("Usage: bannergrab <ip|id> <port> | bannergrab stop")
            return
        sub = args[0].lower()
        if sub == "stop":
            if not self._bannergrab_running:
                self.console.warning("No bannergrab is running.")
                return
            self._bannergrab_running = False
            self.console.info("Bannergrab stop requested")
            return
        if len(args) < 2:
            self.console.body("Usage: bannergrab <ip|id> <port> | bannergrab stop")
            return
        target, port_str = args[0], args[1]
        try:
            port = int(port_str)
        except ValueError:
            self.console.error("Invalid port number")
            return
        machine = None
        if re.match(r"^\d+$", target):
            mid = int(target)
            for m in store.get_all():
                if m.id == mid:
                    machine = m
                    break
        else:
            machine = store.get(target)
        if not machine:
            self.console.warning(f"No machine found for: {target}")
            return
        ip = machine.ip
        if self._bannergrab_running:
            self.console.warning("A bannergrab is already running.")
            return
        self._bannergrab_running = True
        threading.Thread(target=self._run_bannergrab, args=(ip, port, machine), daemon=True).start()

    def _run_bannergrab(self, ip, port, machine):
        probes = [
            ("hello\r\n", "hello"),
            ("GET / HTTP/1.0\r\nHost: {ip}\r\n\r\n", "HTTP GET"),
            (bytes([0x16, 0x03, 0x01, 0x00, 0x01, 0x01, 0x00, 0x03, 0x03] + [0x00]*36), "TLS ClientHello"),
            ("SSH-2.0-OpenSSH_client\r\n", "SSH hello"),
            ("EHLO test\r\n", "SMTP EHLO"),
            ("USER anonymous\r\n", "FTP USER"),
            ("PING\r\n", "Redis PING"),
            ("CAPA\r\n", "POP3 CAPA"),
            ("a001 CAPABILITY\r\n", "IMAP CAPABILITY"),
            ("INFO\r\n", "Redis INFO"),
            ("stats\r\n", "Memcached stats"),
            ("QUIT\r\n", "QUIT"),
            ("\x01\x00\x00\x01\x01", "RDP connect"),
            (b"\x00\x00\x00\xa4\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x0d\x00\x00\x00\x08", "PostgreSQL startup"),
            (b"\x00\x00\x00\x85\xffSMBr\x00\x00\x00\x00\x18", "SMB negotiate"),
            ("RFB 003.008\n", "VNC RFB"),
            (b"\x00" * 36, "MySQL handshake"),
            ('{"isMaster": 1}', "MongoDB isMaster"),
            ('{"buildinfo": 1}', "MongoDB buildInfo"),
            ("GET /version HTTP/1.0\r\nHost: {ip}\r\n\r\n", "Docker API"),
            ("GET /_cluster/health HTTP/1.0\r\nHost: {ip}\r\n\r\n", "Elasticsearch"),
            ("HELP\r\n", "generic HELP"),
            ("STATUS\r\n", "generic STATUS"),
            ("OPTIONS / HTTP/1.0\r\nHost: {ip}\r\n\r\n", "HTTP OPTIONS"),
            ("OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n", "RTSP OPTIONS"),
            ("OPTIONS sip:test@{ip} SIP/2.0\r\nVia: SIP/2.0/TCP test\r\nFrom: <sip:test@test>\r\nTo: <sip:test@test>\r\nCall-ID: 1@test\r\nCSeq: 1 OPTIONS\r\n\r\n", "SIP OPTIONS"),
            ("\xff\xfb\x01\xff\xfb\x03\xff\xfd\x18", "Telnet options"),
            ("\x00\x00\x00\x01", "MySQL login"),
        ]
        self.console.after(0, lambda: self.console.info(f"Bannergrab {ip}:{port} starting ({len(probes)} probes)..."))
        try:
            for payload, label in probes:
                if not self._bannergrab_running:
                    self.console.after(0, lambda: self.console.warning(f"Bannergrab {ip}:{port} stopped"))
                    return
                if isinstance(payload, str):
                    payload_bytes = payload.replace("{ip}", ip).encode()
                else:
                    payload_bytes = payload
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                try:
                    sock.connect((ip, port))
                    # Passive read first
                    sock.setblocking(False)
                    try:
                        passive = sock.recv(4096)
                    except (BlockingIOError, socket.timeout):
                        passive = b""
                    sock.setblocking(True)
                    # Send probe if nothing received passively
                    if passive:
                        response = passive
                    else:
                        try:
                            sock.sendall(payload_bytes)
                            sock.settimeout(2)
                            response = b""
                            while True:
                                try:
                                    chunk = sock.recv(4096)
                                    if not chunk:
                                        break
                                    response += chunk
                                except socket.timeout:
                                    break
                        except (OSError, ConnectionError):
                            response = b""
                except (OSError, ConnectionError, socket.timeout) as e:
                    self.console.after(0, lambda l=label: self.console.body(f"  [{l}] connection failed"))
                    sock.close()
                    continue
                sock.close()
                text = response.decode(errors="replace").strip()
                if text:
                    machine_db.save_banner(machine.id, port, text, label)
                    self.console.after(0, lambda t=text, l=label: self._show_banner_result(ip, port, t, l))
                else:
                    self.console.after(0, lambda l=label: self.console.body(f"  [{l}] no response"))
        finally:
            self._bannergrab_running = False
            self.console.after(0, lambda: self.console.info(f"Bannergrab {ip}:{port} finished"))

    def _show_banner_result(self, ip, port, text, label):
        self.console.after(0, lambda: self.console.success(f"Banner from {ip}:{port} ({label}):"))
        for line in text.split("\n")[:10]:
            self.console.after(0, lambda l=line: self.console.body(f"  {l}"))

    def _scan_list(self):
        machines = store.get_all_sorted()
        if not machines:
            self.console.warning("No machines discovered yet.")
            return
        self.console.title(f"Discovered machines ({len(machines)})")
        for m in machines:
            d = m.to_dict()
            self.console.body(
                f"  {d['ip']:<20} {d['hostname']:<20} {','.join(d['methods']):<20} "
                f"first: {d['first_seen']}  last: {d['last_seen']}"
            )

    def _on_host_discovered(self, ip, hostname, method, mac=""):
        if ip == "ERROR":
            event_bus.submit({"type": "scan_error", "message": hostname})
            return

        if ip in ("127.0.0.1", "::1", "localhost") or ip.startswith("127."):
            return

        existing = store.get(ip)
        machine = store.add_or_update(ip=ip, hostname=hostname, mac=mac, method=method)

        _dbg(f"[discovery] ip={ip} hostname={hostname} method={method} is_new={existing is None} prev_type={existing.device_type if existing else 'N/A'}")

        if ip in self._identifying_ips:
            return

        event_bus.submit({
            "type": "discovery",
            "machine": machine,
            "is_new": existing is None,
        })
        if existing is None or existing.device_type in ("", "device unknown", "iOS device"):
            self._identifying_ips.add(ip)
            threading.Thread(target=self._identify, args=(machine,), daemon=True).start()

    def _identify(self, machine):
        _dbg(f"[identify-start] {machine.ip}  hostname={machine.hostname}")
        old_type = machine.device_type
        try:
            gateway = get_gateway_ip()
            result = identify_device(machine.ip, gateway_ip=gateway, hostname=machine.hostname)
            _dbg(f"[identify-done]  {machine.ip}  result={result!r}")
            if result:
                machine.device_type = result
                model = extract_model_for_ip(machine.ip, resolve=True)
                if model:
                    machine.model = model
                if result == "Windows machine":
                    os_info, domain, server_name = _probe_smb_info(machine.ip)
                    if os_info:
                        machine.device_type = os_info
                        machine.os = os_info
                    if domain:
                        machine.domain = domain
                        domain_db.init_or_update(domain, machine.id, machine.ip, "smb")
                        machine_db.save_domain(machine.id, domain, "smb")
                        machine.hostname = server_name
                if result == "Linux device":
                    banner = _probe_ssh_banner(machine.ip)
                    if banner:
                        distro = _identify_linux_distro(banner)
                        if distro:
                            machine.device_type = distro
                            machine.os = distro
                machine_db.save_machine_info(machine)
                if result != old_type:
                    event_bus.submit({
                        "type": "identify_result",
                        "machine": machine,
                        "result": machine.device_type,
                    })
        finally:
            self._identifying_ips.discard(machine.ip)

    def _process_scanner_events(self, events):
        discoveries = []
        identify_results = []
        scan_ip_results = []
        scan_errors = []

        for ev in events:
            t = ev["type"]
            if t == "discovery":
                discoveries.append(ev)
            elif t == "identify_result":
                identify_results.append(ev)
            elif t == "scan_ip_result":
                scan_ip_results.append(ev)
            elif t == "scan_error":
                scan_errors.append(ev)

        for ev in scan_errors:
            self.console.error(ev["message"])

        for ev in discoveries:
            m = ev["machine"]
            if ev.get("is_new"):
                self.console.success(
                    f"{m.ip:<20} {m.hostname:<20} [{', '.join(m.methods)}]"
                )

        for ev in scan_ip_results:
            m = ev["machine"]
            self.console.success(
                f"{m.ip:<20} {m.hostname:<20} [manual]"
            )

        for ev in identify_results:
            m = ev["machine"]
            result = ev["result"]
            if result == "device unknown":
                self.console.body(f"  {m.ip:<20} identified as: {result}")
            else:
                self.console.success(f"  {m.ip:<20} identified as: {result}")

    def _cmd_init(self, args):
        self._run_init_checks()

    def _cmd_exit(self, args):
        self.destroy()

    def _run_system(self, cmd):
        threading.Thread(target=self._run_system_thread, args=(cmd,), daemon=True).start()

    def _run_system_thread(self, cmd):
        _dbg(f"[system] started: {cmd}")
        args = cmd.split()
        monitor_nmap = None
        if args and args[0].lower() == "nmap":
            for arg in args[1:]:
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", arg):
                    machine = store.get(arg)
                    if machine:
                        monitor_nmap = machine
                        _dbg(f"[system] nmap monitoring for machine #{machine.id} ({arg})")
                    break
        try:
            shell = os.environ.get("SHELL", "/bin/sh")
            proc = subprocess.Popen(
                [shell, "-i", "-c", cmd],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1,
            )
            self._system_process = proc
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.console.after(0, lambda l=stripped: self.console.body(l))
                if monitor_nmap:
                    m = re.match(r"Discovered open port (\d+)/(tcp|udp) on \S+", stripped)
                    if m:
                        port = int(m.group(1))
                        proto = m.group(2)
                        if proto == "udp":
                            if machine_db.save_udp_port(monitor_nmap.id, port):
                                self.console.after(0, lambda p=port, mid=monitor_nmap.id: self.console.success(
                                    f"  nmap: added UDP port {p} to machine #{mid}"
                                ))
                        else:
                            if machine_db.save_tcp_port(monitor_nmap.id, port):
                                self.console.after(0, lambda p=port, mid=monitor_nmap.id: self.console.success(
                                    f"  nmap: added port {p} to machine #{mid}"
                                ))
            proc.wait()
            if self._system_process is proc:
                self._system_process = None
            if proc.returncode != 0:
                self.console.after(0, lambda: self.console.warning(f"exit code: {proc.returncode}"))
        except Exception as e:
            self.console.after(0, lambda: self.console.error(f"System command failed: {e}"))

    def _stop_system(self):
        if self._system_process:
            self._system_process.kill()
            self.console.info("Process stopped")

    def _cmd_ping(self, args):
        if not args:
            self.console.body("Usage: ping <ip|id>")
            return
        target = args[0]
        ip = target
        if re.match(r"^\d+$", ip):
            mid = int(ip)
            for m in store.get_all():
                if m.id == mid:
                    ip = m.ip
                    break
            else:
                self.console.warning(f"No machine with ID #{mid}")
                return
        threading.Thread(target=self._run_ping, args=(ip,), daemon=True).start()

    def _run_ping(self, ip):
        if self._is_root():
            self._run_ping_scapy(ip)
        elif shutil.which("ping"):
            self._run_ping_system(ip)
        else:
            self.console.after(0, lambda: self.console.error(
                "No root privileges and 'ping' command not found in system"
            ))

    def _run_ping_scapy(self, ip):
        from scapy.all import sr1, IP, ICMP
        self.console.after(0, lambda: self.console.info(f"Pinging {ip} (scapy ICMP)..."))
        try:
            start = time.monotonic()
            reply = sr1(IP(dst=ip) / ICMP(), timeout=2, verbose=False)
            elapsed = time.monotonic() - start
            if reply is None:
                self.console.after(0, lambda: self.console.warning(f"{ip} no response"))
            else:
                rtt_ms = elapsed * 1000
                ttl = reply.ttl
                self.console.after(0, lambda: self.console.success(
                    f"Reply from {ip}: time={rtt_ms:.1f}ms  ttl={ttl}"
                ))
        except Exception as e:
            self.console.after(0, lambda: self.console.error(f"Ping {ip} failed: {e}"))

    def _run_ping_system(self, ip):
        if platform.system().lower() == "windows":
            cmd = ["ping", "-n", "1", ip]
        else:
            cmd = ["ping", "-c", "1", ip]
        self.console.after(0, lambda: self.console.info(f"Pinging {ip}..."))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = proc.stdout + proc.stderr
            _dbg(f"[ping] returncode={proc.returncode}\n{output}")
            for line_raw in output.splitlines():
                stripped = line_raw.rstrip()
                if stripped:
                    self.console.after(0, lambda l=stripped: self.console.body(l))
            if proc.returncode != 0:
                self.console.after(0, lambda: self.console.warning(f"{ip} no response"))
        except subprocess.TimeoutExpired:
            self.console.after(0, lambda: self.console.warning(f"{ip} ping timed out"))
        except Exception as e:
            self.console.after(0, lambda: self.console.error(f"Ping {ip} failed: {e}"))

    def _cmd_nslookup(self, args):
        if not args:
            self.console.body("Usage: nslookup <domain|ip|id>")
            return
        target = args[0]
        if re.match(r"^\d+$", target):
            mid = int(target)
            for m in store.get_all():
                if m.id == mid:
                    target = m.ip
                    break
            else:
                self.console.warning(f"No machine with ID #{mid}")
                return
        threading.Thread(target=self._run_nslookup, args=(target,), daemon=True).start()

    def _run_nslookup(self, target):
        self.console.after(0, lambda: self.console.info(f"nslookup {target}..."))
        try:
            proc = subprocess.run(
                ["nslookup", target], capture_output=True, text=True, timeout=10
            )
            output = proc.stdout + proc.stderr
            _dbg(f"[nslookup] returncode={proc.returncode}\n{output}")
            for line_raw in output.splitlines():
                stripped = line_raw.rstrip()
                if stripped:
                    self.console.after(0, lambda l=stripped: self.console.body(l))
            if proc.returncode != 0:
                self.console.after(0, lambda: self.console.warning(f"nslookup {target} failed"))
        except subprocess.TimeoutExpired:
            self.console.after(0, lambda: self.console.warning(f"nslookup {target} timed out"))
        except Exception as e:
            self.console.after(0, lambda: self.console.error(f"nslookup {target} failed: {e}"))

    def _cmd_domain(self, args):
        if not args:
            self.console.body("Usage: add-domain <name>")
            return
        domain = args[0].strip()
        threading.Thread(target=self._run_domain, args=(domain,), daemon=True).start()

    def _cmd_add(self, args):
        if not args:
            self.console.body("Usage: add <machine|domain|credential|user|password|hash>")
            return
        sub = args[0].lower()
        rest = args[1:]
        if sub == "machine":
            self._cmd_add_machine(rest)
        elif sub == "domain":
            self._cmd_domain(rest)
        elif sub == "credential":
            self._cmd_add_credential(rest)
        elif sub == "user":
            self._cmd_add_user(rest)
        elif sub == "password":
            self._cmd_add_password(rest)
        elif sub == "hash":
            self._cmd_add_hash(rest)
        else:
            self.console.error(f"Unknown add target: {sub}")

    def _run_domain(self, domain):
        self.console.after(0, lambda: self.console.info(f"Resolving {domain}..."))
        try:
            info = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
            if not info:
                self.console.after(0, lambda: self.console.warning(f"{domain} could not be resolved"))
                return
            ip = info[0][4][0]
        except socket.gaierror:
            self.console.after(0, lambda: self.console.warning(f"{domain} could not be resolved"))
            return

        machine = store.get(ip)
        if machine:
            machine_db.save_domain(machine.id, domain, "manual")
            domain_db.init_or_update(domain, machine.id, machine.ip, "manual")
            self.console.after(0, lambda: self.console.success(
                f"{domain} → {ip}  (added to machine #{machine.id})"
            ))
        else:
            machine = store.add_or_update(ip=ip, method="manual")
            machine.device_type = "device unknown"
            machine_db.save_machine_info(machine)
            machine_db.save_domain(machine.id, domain, "manual")
            domain_db.init_or_update(domain, machine.id, machine.ip, "manual")
            self.console.after(0, lambda: self.console.success(
                f"{domain} → {ip}  (new machine #{machine.id})"
            ))

    def _cmd_add_machine(self, args):
        if not args:
            self.console.body("Usage: add machine <ip>")
            return
        ip = args[0]
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
            self.console.body("Usage: add machine <ip>")
            return
        machine = store.add_or_update(ip=ip, method="manual")
        machine.device_type = "device unknown"
        machine_db.save_machine_info(machine)
        self.console.success(f"Machine #{machine.id} ({ip}) added")

    def _cmd_add_credential(self, args):
        from src.machines.credential_db import save_credential, save_user
        if len(args) < 2:
            self.console.body("Usage: add credential <username> <password|hash_nt>")
            return
        username = args[0]
        secret = args[1]
        nt_pattern = re.compile(r"^[a-fA-F0-9]{32}$")
        if nt_pattern.match(secret):
            cid = save_credential(username, "", hash_nt=secret, hash_nt_origin="manual")
            self.console.success(f"Credential #{cid}: {username} (NT hash) added")
        else:
            cid = save_credential(username, secret, password_origin="manual")
            self.console.success(f"Credential #{cid}: {username} / {secret} added")
        save_user(username)

    def _cmd_add_user(self, args):
        if not args:
            self.console.body("Usage: add user <username>")
            return
        from src.machines.credential_db import save_user
        save_user(args[0])
        self.console.success(f"User '{args[0]}' added")

    def _cmd_add_password(self, args):
        if not args:
            self.console.body("Usage: add password <password>")
            return
        from src.machines.credential_db import save_password
        save_password(args[0])
        self.console.success("Password added")

    def _cmd_add_hash(self, args):
        if len(args) < 2:
            self.console.body("Usage: add hash <type> <hash>")
            return
        from src.machines.credential_db import save_hash_entry
        hid = save_hash_entry(args[0], args[1], origin="manual")
        self.console.success(f"Hash #{hid} added")

    def _cmd_fuzz(self, args):
        from .dialogs.fuzz import FuzzDialog
        FuzzDialog(self)

    def _cmd_ftp(self, args):
        if not args:
            from .dialogs.remote_access import RemoteAccessDialog
            RemoteAccessDialog(self)
            self.visualizer.activate_view("shells")
            return

        target = args[0]
        ip = target
        if re.match(r"^\d+$", ip):
            machine_id = int(ip)
            machine = None
            for m in store.get_all():
                if m.id == machine_id:
                    machine = m
                    break
            if machine:
                ip = machine.ip
            else:
                self.console.warning(f"No machine with ID #{machine_id}")
                return

        port = 21
        cred_user = ""
        cred_pass = ""
        if len(args) >= 2:
            if re.match(r"^\d+$", args[1]):
                port = int(args[1])
                if len(args) >= 3:
                    cred_user = args[2]
            else:
                cred_user = args[1]

        if cred_user:
            from src.machines import credential_db
            for c in credential_db.load_credentials():
                if c.get("username") == cred_user:
                    cred_pass = c.get("password") or ""
                    break

        self.console.info(f"Connecting FTP to {ip}:{port}...")
        threading.Thread(
            target=self._run_ftp_connect,
            args=(ip, port, cred_user, cred_pass),
            daemon=True,
        ).start()
        self.visualizer.activate_view("shells")

    def _run_ftp_connect(self, host, port, user, password):
        from src.shells.ftp_shell import FTPConnectionThread

        def on_connected(sid):
            self.console.after(0, lambda: self.console.success(
                f"FTP session #{sid} to {host}:{port}"
            ))

        def on_error(msg):
            self.console.after(0, lambda: self.console.error(f"FTP failed: {msg}"))

        ftp_thread = FTPConnectionThread(
            host, port, user, password,
            on_connected=on_connected,
            on_error=on_error,
        )
        ftp_thread.start()

    def _cmd_recorder(self, args):
        if not args:
            from src.tools.webrecorder import find_browsers
            from .dialogs.recorder_dialog import WebRecorderDialog
            browsers = find_browsers()
            if not browsers:
                self.console.error(
                    "No supported browser found (chromium-based). Install Chrome, Chromium, or Brave."
                )
                return
            dialog = WebRecorderDialog(self, browsers)
            if not dialog.result:
                return
            threading.Thread(target=self._run_recorder_dialog, args=(dialog.result,), daemon=True).start()
            return
        sub = args[0].lower()
        if sub == "stop":
            if self._recorder and self._recorder.is_running():
                self._recorder.stop()
                self._recorder.kill_browser()
                self._recorder = None
                self.console.info("Recorder stopped")
            else:
                self.console.warning("No webrecorder is running.")
            return
        target = sub
        if re.match(r"^\d+$", target):
            mid = int(target)
            for m in store.get_all():
                if m.id == mid:
                    target = m.ip
                    break
            else:
                self.console.warning(f"No machine with ID #{mid}")
                return
        if self._recorder and self._recorder.is_running():
            self.console.warning("A webrecorder is already running. Use 'webrecorder stop' first.")
            return
        threading.Thread(target=self._run_recorder, args=(target,), daemon=True).start()

    def _run_recorder_dialog(self, config):
        from src.tools.webrecorder import Recorder
        import tkinter as tk
        import threading

        name = config["name"]
        target = config["target"]
        browser_path = config["browser"]
        scope = config.get("scope")
        review_outgoing = config.get("review_mode", False)
        review_incoming = config.get("review_mode", False)

        label = os.path.basename(browser_path)
        self.console.after(0, lambda l=label: self.console.info(f"Using {l}"))

        def on_log(text, color=None):
            if color == "success":
                self.console.after(0, lambda t=text: self.console.success(t.rstrip()))
            elif color == "error":
                self.console.after(0, lambda t=text: self.console.error(t.rstrip()))
            elif color == "info":
                self.console.after(0, lambda t=text: self.console.info(t.rstrip()))
            else:
                self.console.after(0, lambda t=text: self.console.body(t.rstrip()))

        review_mgr = _ReviewDialogManager(self)
        if review_outgoing or review_incoming:
            review_mgr.show_waiting()

        def on_review_request(url, method, headers, body, res_type, net_id, stage, on_send,
                               resp_status=None, resp_status_text=None, resp_headers=None,
                               resp_body=""):
            done = threading.Event()
            review_mgr.add(url, method, headers, body, res_type, stage, on_send, done,
                           resp_status, resp_status_text, resp_headers, resp_body)
            done.wait()

        review_kw = {}
        if review_outgoing or review_incoming:
            review_kw["review_mode"] = True
            review_kw["on_review_request"] = on_review_request

        self._recorder = Recorder(target, browser_path, on_log=on_log, evidence_name=name,
                                   scope=scope, **review_kw)
        self._recorder.start()

        while self._recorder and self._recorder.is_running():
            import time
            time.sleep(1)
        review_mgr.close()

    def _run_recorder(self, target):
        from src.tools.webrecorder import find_browsers, BrowserSelector, Recorder
        from src.tools.webrecorder import evidence

        browsers = find_browsers()
        if not browsers:
            self.console.after(0, lambda: self.console.error(
                "No supported browser found (chromium-based). Install Chrome, Chromium, or Brave."
            ))
            return

        if len(browsers) > 1:
            dialog = BrowserSelector(self, browsers)
            if not dialog.result:
                self.console.after(0, lambda: self.console.warning("Recorder cancelled."))
                return
            browser_path = dialog.result
        else:
            browser_path = list(browsers.keys())[0]

        label = list(browsers.values())[0] if len(browsers) == 1 else os.path.basename(browser_path)
        self.console.after(0, lambda l=label: self.console.info(f"Using {l}"))

        def on_log(text, color=None):
            if color == "success":
                self.console.after(0, lambda t=text: self.console.success(t.rstrip()))
            elif color == "error":
                self.console.after(0, lambda t=text: self.console.error(t.rstrip()))
            elif color == "info":
                self.console.after(0, lambda t=text: self.console.info(t.rstrip()))
            else:
                self.console.after(0, lambda t=text: self.console.body(t.rstrip()))

        self._recorder = Recorder(target, browser_path, on_log=on_log)
        self._recorder.start()

    def _cmd_delete(self, args):
        if not args:
            self.console.body("Usage: delete <dbs|credentials|evidences>")
            return
        sub = args[0].lower()
        if sub == "dbs":
            self._cmd_delete_dbs(args[1:])
        elif sub == "credential":
            self._cmd_delete_credential(args[1:])
        elif sub == "evidence":
            self._cmd_delete_evidence_single(args[1:])
        elif sub == "hash":
            self._cmd_delete_hash(args[1:])
        elif sub == "machine":
            self._cmd_delete_machine(args[1:])
        elif sub == "domain":
            self._cmd_delete_domain(args[1:])
        elif sub == "user":
            self._cmd_delete_user(args[1:])
        elif sub == "password":
            self._cmd_delete_password(args[1:])
        elif sub == "shell":
            self._cmd_delete_shell(args[1:])
        else:
            self.console.error(f"Unknown delete target: {sub}. Use: dbs, credential, evidence, hash, machine, domain, user, password, shell")

    def _cmd_delete_creds(self, args):
        from src.machines.credential_db import delete_all
        delete_all()
        self.console.info("All credentials data cleared")

    def _cmd_delete_credential(self, args):
        if not args:
            self.console.body("Usage: delete credential <username|all>")
            return
        from src.machines.credential_db import load_credentials, delete_credential
        username = args[0]
        if username == "all":
            from src.machines.credential_db import delete_all
            delete_all()
            self.console.info("All credentials deleted")
            return
        for c in load_credentials():
            if c["username"] == username:
                delete_credential(c["id"])
                self.console.success(f"Credential '{username}' deleted")
                return
        self.console.warning(f"No credential found for: {username}")

    def _cmd_delete_evidence_single(self, args):
        import shutil
        from src.hsf_paths import evidence_dir
        if not args:
            self.console.body("Usage: delete evidence <name|all>")
            return
        name = args[0]
        base = str(evidence_dir())
        if name == "all":
            if os.path.isdir(base):
                shutil.rmtree(base)
                os.makedirs(base, exist_ok=True)
            self.console.info("All evidence data cleared")
            return
        path = os.path.join(base, name)
        if not os.path.isdir(path):
            self.console.warning(f"No evidence session found: {name}")
            return
        shutil.rmtree(path)
        self.console.success(f"Evidence '{name}' deleted")

    def _cmd_delete_hash(self, args):
        if not args:
            self.console.body("Usage: delete hash <hash|id|all>")
            return
        from src.machines.credential_db import load_hashes, delete_hash_entry
        target = args[0]
        if target == "all":
            count = 0
            for h in list(load_hashes()):
                delete_hash_entry(h["id"])
                count += 1
            self.console.success(f"{count} hashes deleted")
            return
        for h in load_hashes():
            if h["hash"] == target:
                delete_hash_entry(h["id"])
                self.console.success(f"Hash deleted (id={h['id']})")
                return
        if target.isdigit():
            hid = int(target)
            delete_hash_entry(hid)
            self.console.success(f"Hash #{hid} deleted")
            return
        self.console.warning(f"No hash found matching: {target}")

    def _cmd_delete_machine(self, args):
        if not args:
            self.console.body("Usage: delete machine <id|ip|all>")
            return
        target = args[0]
        if target == "all":
            count = 0
            for m in list(store.get_all()):
                machine_db.delete_machine_db(m.id)
                store.remove(m.ip)
                count += 1
            self.console.success(f"{count} machines deleted")
            return
        machine = store.get(target)
        if not machine and target.isdigit():
            mid = int(target)
            for m in store.get_all():
                if m.id == mid:
                    machine = m
                    break
        if not machine:
            self.console.warning(f"No machine found for: {target}")
            return
        machine_db.delete_machine_db(machine.id)
        store.remove(machine.ip)
        self.console.success(f"Machine #{machine.id} ({machine.ip}) deleted")

    def _cmd_delete_shell(self, args):
        if not args:
            self.console.body("Usage: delete shell <id|ip|all>")
            return
        from src.shells import shell_db
        target = args[0]
        if target == "all":
            count = 0
            for s in list(shell_db.get_all()):
                shell_db.close_session(s["id"])
                count += 1
            self.console.success(f"{count} shells closed")
            return
        session = None
        for s in shell_db.get_all():
            if s["ip"] == target:
                session = s
                break
        if not session and target.isdigit():
            sid = int(target)
            session = shell_db.get_session(sid)
        if not session:
            self.console.warning(f"No shell found for: {target}")
            return
        shell_db.close_session(session["id"])
        self.console.success(f"Shell #{session['id']} ({session['ip']}) closed")

    def _cmd_delete_domain(self, args):
        if not args:
            self.console.body("Usage: delete domain <domain|all>")
            return
        domain = args[0]
        if domain == "all":
            count = 0
            for d in list(domain_db.list_all()):
                domain_db.delete_domain(d)
                count += 1
            self.console.success(f"{count} domains deleted")
            return
        if not domain_db.exists(domain):
            self.console.warning(f"No domain found for: {domain}")
            return
        domain_db.delete_domain(domain)
        self.console.success(f"Domain '{domain}' deleted")

    def _cmd_delete_user(self, args):
        if not args:
            self.console.body("Usage: delete user <username|all>")
            return
        from src.machines.credential_db import delete_user, load_users
        username = args[0]
        if username == "all":
            count = 0
            for u in list(load_users()):
                delete_user(u)
                count += 1
            self.console.success(f"{count} users deleted")
            return
        if username not in load_users():
            self.console.warning(f"No user found for: {username}")
            return
        delete_user(username)
        self.console.success(f"User '{username}' deleted")

    def _cmd_delete_password(self, args):
        if not args:
            self.console.body("Usage: delete password <password|all>")
            return
        from src.machines.credential_db import delete_password, load_passwords
        pwd = args[0]
        if pwd == "all":
            count = 0
            for p in list(load_passwords()):
                delete_password(p)
                count += 1
            self.console.success(f"{count} passwords deleted")
            return
        if pwd not in load_passwords():
            self.console.warning(f"No password found")
            return
        delete_password(pwd)
        self.console.success("Password deleted")

    def _cmd_delete_evidence(self, args):
        import shutil
        from src.tools.webrecorder.evidence import target_dir
        evidence_dir = target_dir(".")
        evidence_dir = os.path.dirname(evidence_dir)
        if os.path.isdir(evidence_dir):
            shutil.rmtree(evidence_dir)
            os.makedirs(evidence_dir, exist_ok=True)
            self.console.info("All evidence data cleared")
        else:
            self.console.info("Evidence directory not found")

    def _cmd_delete_dbs(self, args):
        store.clear()
        clear_mdns_cache()
        machine_db.delete_all()
        domain_db.delete_all()
        from src.machines.credential_db import delete_all as del_creds
        del_creds()
        wipe_mdns_cache()
        stop_machines_autosave()
        start_machines_autosave(store)
        self.console.info("All data cleared (mDNS cache + machine list + database files)")

    def _on_close(self):
        if self._passive_scanner:
            self._passive_scanner.stop()
        if self._active_scanner:
            self._active_scanner.stop()
        if self._shell_listener:
            self._shell_listener.stop()
        self._udpscan_running = False
        self._tcpscan_running = False
        stop_machines_autosave()
        store.save()
        save_mdns_cache()
        hsf_settings.save()
        event_bus.stop()
        self.destroy()
