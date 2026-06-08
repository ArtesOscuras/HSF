import ipaddress
import os
import re
import shutil
import socket
import subprocess
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
import netifaces
from .console import Console
from .visualizer import Visualizer
from .views import NetworkView
from .dialogs import InterfaceSelector
from src.machines import store, start_autosave as start_machines_autosave
from src.machines import machine_db
import src.machines
from src.scanner import PassiveMDNSScanner, ActiveScanner
from src.scanner.mdns_cache import load as load_mdns_cache, save as save_mdns_cache, start_autosave, wipe as wipe_mdns_cache
from src.identifier import identify_device, get_gateway_ip, extract_model_for_ip, _probe_smb_info, _probe_ssh_banner, _parse_ssh_banner, _probe_ttl, _run_whatweb, _probe_web_internal, _identify_linux_distro, _extract_domains_from_whatweb, _dbg


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

        self.after(100, self._set_initial_sash)

        self._passive_scanner = None
        self._active_scanner = None
        self._selected_interface = None
        self._identifying_ips = set()
        self._tcpscan_running = False
        self._tcpscan_process = None

        self._register_views()
        self.visualizer.activate_view("network")
        self._register_commands()

        load_mdns_cache()
        start_autosave()
        store.load()
        start_machines_autosave(store)

        self.after(500, self._start_passive_scanner)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_initial_sash(self):
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
        self.visualizer.register_view("network", net_view)
        self.console.add_help_section("Views", [
            ("view list", "List available views"),
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
        self.console.register_command("exit", self._cmd_exit, "Close the application")

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
        else:
            try:
                self.visualizer.activate_view(sub)
                self.console.info(f"Switched to view: {sub}")
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
            machine_view._on_back_click = lambda: self.visualizer.activate_view("network")
            self.visualizer.register_view(view_name, machine_view)
        self.visualizer.activate_view(view_name)
        self.console.info(f"Switched to view: machine_{machine.id}")

    def _open_machine_view(self, machine):
        self._cmd_view_machine([str(machine.id)])

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
        from src.scanner.mdns_cache import get_services
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
                self.console.body("Usage: whatweb <ip|id> [port]")
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
        threading.Thread(target=self._run_webscan, args=(ip, port, machine), daemon=True).start()

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

    def _run_webscan(self, ip, port, machine):
        found, mode = self._has_whatweb()
        if found:
            self.console.after(0, lambda: self.console.info(
                f"Web scanning {ip}:{port} (whatweb)..."
            ))
            stdout, stderr = _run_whatweb(ip, port, mode=mode)
            stdout = self._strip_ansi(stdout)
            stderr = self._strip_ansi(stderr)
            if stderr:
                for line in stderr.split("\n"):
                    if line.strip():
                        self.console.after(0, lambda l=line: self.console.error(f"  whatweb: {l}"))
                stdout = stdout + "\n" + stderr if stdout else stderr
            if stdout:
                machine_db.save_web_service(machine.id, port, stdout)
                domains = _extract_domains_from_whatweb(stdout)
                for d in domains:
                    machine_db.save_domain(machine.id, d, "whatweb")
                self.console.after(0, lambda: self.console.info(
                    f"Web scan {ip}:{port} done (whatweb)"
                ))
                for d in domains:
                    self.console.after(0, lambda dom=d: self.console.success(f"  domain: {dom}"))
            else:
                self.console.after(0, lambda: self.console.warning(
                    f"No web service detected at {ip}:{port}"
                ))
        else:
            self.console.after(0, lambda: self.console.error(
                "whatweb not found in path"
            ))
            self.console.after(0, lambda: self.console.info(
                f"Web scanning {ip}:{port} (internal scanner)..."
            ))
            output = _probe_web_internal(ip, port)
            engine = "internal"
            if output:
                machine_db.save_web_service(machine.id, port, output)
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
        if len(args) < 2:
            self.console.body("Usage: bannergrab <ip|id> <port>")
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
        threading.Thread(target=self._run_bannergrab, args=(ip, port), daemon=True).start()

    def _run_bannergrab(self, ip, port):
        self.console.after(0, lambda: self.console.info(f"Connecting to {ip}:{port}..."))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((ip, port))
            banner = b""
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    banner += chunk
                except socket.timeout:
                    break
            sock.close()
        except Exception as e:
            err_msg = str(e)
            self.console.after(0, lambda m=err_msg: self.console.error(f"  {ip}:{port} connection failed: {m}"))
            return
        text = banner.decode(errors="replace").strip()
        if text:
            self.console.after(0, lambda: self.console.success(f"Banner from {ip}:{port}:"))
            for line in text.split("\n"):
                self.console.after(0, lambda l=line: self.console.body(f"  {l}"))
        else:
            self.console.after(0, lambda: self.console.warning(f"No banner received from {ip}:{port}"))

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

    def _cmd_exit(self, args):
        self.destroy()

    def _cmd_delete_dbs(self, args):
        store.clear()
        wipe_mdns_cache()
        machine_db.delete_all()
        self.console.info("All data cleared (mDNS cache + machine list + database files)")

    def _on_close(self):
        if self._passive_scanner:
            self._passive_scanner.stop()
        if self._active_scanner:
            self._active_scanner.stop()
        store.save()
        save_mdns_cache()
        self.destroy()
