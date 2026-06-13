import ipaddress
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
from .console import Console
from .visualizer import Visualizer
from .views import NetworkView, DomainListView, EvidenceListView, CredentialListView, UserPassView, HashListView, ToolsView
from .dialogs import InterfaceSelector
from src.machines import store, start_autosave as start_machines_autosave
from src.machines import machine_db
from src.machines import domain_db
import src.machines
from src.tools.scanner import PassiveMDNSScanner, ActiveScanner
from src.tools.scanner.mdns_cache import load as load_mdns_cache, save as save_mdns_cache, start_autosave, clear as clear_mdns_cache, wipe as wipe_mdns_cache
from src.tools.scanner.identifier import identify_device, get_gateway_ip, extract_model_for_ip, _probe_smb_info, _probe_ssh_banner, _parse_ssh_banner, _probe_ttl, _run_whatweb, _probe_web_internal, _identify_linux_distro, _extract_domains_from_whatweb, _dbg


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HSF - Hack Station Framework")
        self.minsize(800, 600)
        self.state("zoomed")

        self.configure(bg="#000000")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._pane = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#2d2d2d",
                                     sashwidth=5, sashrelief=tk.FLAT, borderwidth=0)
        self._pane.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.visualizer = Visualizer(self._pane)
        self._pane.add(self.visualizer, stretch="always")

        self.console = Console(self._pane)
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
        self._bannergrab_running = False

        self._register_views()
        self.visualizer.activate_view("tools")
        self._register_commands()

        load_mdns_cache()
        start_autosave()
        store.load()
        start_machines_autosave(store)

        self.after(500, self._run_init_checks)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _run_init_checks(self):
        from .dialogs.init_dialog import InitDialog
        dialog = InitDialog(self)
        self.wait_window(dialog)
        if self._passive_scanner is None or not self._passive_scanner.is_running:
            self._start_passive_scanner()

    def _set_initial_sash(self):
        self.update_idletasks()
        h = self.winfo_height()
        if h > 100:
            self._pane.sash_place(0, 0, h * 2 // 3)

    def _start_passive_scanner(self):
        self._passive_scanner = PassiveMDNSScanner(on_host_callback=self._on_host_discovered)
        self._passive_scanner.start()
        self.console.info("Passive listening mDNS started")

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

        self.console.add_help_section("Views", [
            ("view list", "List available views"),
            ("view machines", "Machine list"),
            ("view domains", "Discovered domains list"),
            ("view tools", "Available tools"),
            ("view evidences", "Evidence sessions list"),
            ("view credentials", "Stored credentials"),
            ("view machine <id|ip>", "View machine details"),
            ("view <name>", "Switch to a view"),
        ])

    def _register_commands(self):
        self.console.register_command("view", self._cmd_view, "Switch or list views")
        self.console.register_command("scan", self._cmd_scan, "Network scanning commands")
        self.console.register_command("tcpscan", self._cmd_tcpscan, "Scan TCP ports on an IP")
        self.console.register_command("whatweb", self._cmd_whatweb, "Web technology scan on a port")
        self.console.register_command("bannergrab", self._cmd_bannergrab, "Grab service banner from a port")
        self.console.register_command("delete-dbs", self._cmd_delete_dbs, "Wipe all stored data")
        self.console.register_command("delete-credentials", self._cmd_delete_creds, "Delete all credentials")
        self.console.register_command("ping", self._cmd_ping, "Ping a machine by IP or ID")
        self.console.register_command("nslookup", self._cmd_nslookup, "DNS lookup for a domain, IP or machine ID")
        self.console.register_command("add-domain", self._cmd_domain, "Add a domain to the inventory")
        self.console.register_command("fuzz", self._cmd_fuzz, "Open fuzz configuration dialog")
        self.console.register_command("webrecorder", self._cmd_recorder, "Record browser session for a domain")
        self.console.register_command("delete-evidence", self._cmd_delete_evidence, "Delete all evidence data")
        self.console.register_command("init", self._cmd_init, "Re-run initialization checks")
        self.console.register_command("exit", self._cmd_exit, "Close the application")

        self.console.set_system_handler(self._run_system)
        self.console.set_system_stop_handler(self._stop_system)

    def _cmd_view(self, args):
        if not args:
            self.console.body("Usage: view <name> or view list")
            return
        sub = args[0].lower()
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
            self._cmd_view_machine(args[1:])
        elif sub == "domain":
            self._cmd_view_domain(args[1:])
        else:
            try:
                self.visualizer.activate_view(sub)
            except ValueError:
                self.console.error(f"Unknown view: {sub}. Use 'view list' to see available views.")

    def _cmd_view_machine(self, args):
        if not args:
            self.console.body("Usage: view machine <id|ip>")
            return
        target = args[0]
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
        self._passive_scanner = PassiveMDNSScanner(on_host_callback=self._on_host_discovered)
        self._passive_scanner.start()
        self.console.info("Passive listening mDNS started")

    def _scan_active(self):
        if self._active_scanner and self._active_scanner.is_running:
            self.console.warning("Active scan is already running.")
            return

        iface = self._show_interface_dialog()

        if not iface:
            self.console.warning("Scan cancelled: no interface selected")
            return

        if iface[0] == "ip":
            self._scan_ip(iface[1])
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
                self.console.warning("python-nmap not found: pip install python-nmap")
        except RuntimeError as e:
            self.console.error(str(e))

    def _show_interface_dialog(self):
        dialog = InterfaceSelector(self)
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
            self.console.after(0, lambda: self.console.warning(f"No device detected at {ip}"))
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
        self.console.after(0, lambda: self.console.success(
            f"{machine.ip:<20} {machine.hostname:<20} [manual]"
        ))

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
            self.console.after(0, lambda: self.console.error(hostname))
            return

        if ip in ("127.0.0.1", "::1", "localhost") or ip.startswith("127."):
            return

        existing = store.get(ip)
        is_new = existing is None
        machine = store.add_or_update(ip=ip, hostname=hostname, mac=mac, method=method)

        _dbg(f"[discovery] ip={ip} hostname={hostname} method={method} is_new={is_new} prev_type={existing.device_type if existing else 'N/A'}")

        if ip in self._identifying_ips:
            return

        if is_new:
            self.console.after(0, lambda m=machine: self.console.success(
                f"{m.ip:<20} {m.hostname:<20} [{', '.join(m.methods)}]"
            ))
            self._identifying_ips.add(ip)
            threading.Thread(target=self._identify, args=(machine,), daemon=True).start()
        elif not existing.device_type or existing.device_type in ("device unknown", "iOS device"):
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
                    if machine.device_type == "device unknown":
                        self.console.after(0, lambda m=machine: self.console.body(
                            f"  {m.ip:<20} identified as: {m.device_type}"
                        ))
                    else:
                        self.console.after(0, lambda m=machine: self.console.success(
                            f"  {m.ip:<20} identified as: {m.device_type}"
                        ))
        finally:
            self._identifying_ips.discard(machine.ip)

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
                    m = re.match(r"Discovered open port (\d+)/tcp on \S+", stripped)
                    if m:
                        port = int(m.group(1))
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

    def _cmd_fuzz(self, args):
        from .dialogs.fuzz import FuzzDialog
        FuzzDialog(self)

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

        name = config["name"]
        target = config["target"]
        browser_path = config["browser"]
        scope = config.get("scope")

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

        self._recorder = Recorder(target, browser_path, on_log=on_log, evidence_name=name, scope=scope)
        self._recorder.start()

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

    def _cmd_delete_creds(self, args):
        from src.machines.credential_db import delete_all
        delete_all()
        self.console.info("All credentials data cleared")

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
        self.console.info("All data cleared (mDNS cache + machine list + database files)")

    def _on_close(self):
        if self._passive_scanner:
            self._passive_scanner.stop()
        if self._active_scanner:
            self._active_scanner.stop()
        store.save()
        save_mdns_cache()
        self.destroy()
