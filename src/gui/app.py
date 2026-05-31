import tkinter as tk
import threading
import netifaces
from .console import Console
from .visualizer import Visualizer
from .views import NetworkView
from .dialogs import InterfaceSelector
from src.machines import store
import src.machines
from src.scanner import PassiveMDNSScanner, ActiveScanner
from src.identifier import identify_device


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HSF - Hack Station Framework")
        self.minsize(800, 600)
        self.state("zoomed")

        self.configure(bg="#000000")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=2)
        self.rowconfigure(1, weight=1)

        self.visualizer = Visualizer(self, highlightbackground="#2d2d2d", highlightthickness=1)
        self.visualizer.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.console = Console(self, highlightbackground="#2d2d2d", highlightthickness=1)
        self.console.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        self._passive_scanner = None
        self._active_scanner = None
        self._selected_interface = None

        self._register_views()
        self._register_commands()
        self.after(500, self._start_passive_scanner)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _start_passive_scanner(self):
        self._passive_scanner = PassiveMDNSScanner(on_host_callback=self._on_host_discovered)
        self._passive_scanner.start()
        self.console.info("Passive mDNS scan started")

    def _register_views(self):
        self.visualizer.register_view("network", NetworkView(self.visualizer))
        self.console.add_help_section("Views", [
            ("view list", "List available views"),
            ("view <name>", "Switch to a view"),
        ])

    def _register_commands(self):
        self.console.register_command("view", self._cmd_view, "Switch or list views")
        self.console.register_command("scan", self._cmd_scan, "Network scanning commands")
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
        else:
            try:
                self.visualizer.activate_view(sub)
                self.console.success(f"Switched to view: {sub}")
            except ValueError:
                self.console.error(f"Unknown view: {sub}. Use 'view list' to see available views.")

    def _cmd_scan(self, args):
        if not args:
            self._scan_active()
            return
        sub = args[0].lower()
        if sub == "active":
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
        self.console.info("Passive mDNS scan started")

    def _scan_active(self):
        if self._active_scanner and self._active_scanner.is_running:
            self.console.warning("Active scan is already running.")
            return

        iface = self._selected_interface
        if not iface:
            self.console.info("No interface selected. Choose one:")
            iface = self._show_interface_dialog()

        if not iface:
            self.console.warning("Scan cancelled: no interface selected")
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
        except RuntimeError as e:
            self.console.error(str(e))

    def _show_interface_dialog(self):
        dialog = InterfaceSelector(self)
        return dialog.result

    def _scan_stop(self):
        stopped = False
        if self._active_scanner and self._active_scanner.is_running:
            self._active_scanner.stop()
            self._active_scanner = None
            stopped = True
        if self._passive_scanner and self._passive_scanner.is_running:
            self._passive_scanner.stop()
            self._passive_scanner = None
            stopped = True
        if stopped:
            self.console.info("Scan stopped")
        else:
            self.console.warning("No scan is running.")

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

        existing = store.get(ip)
        is_new = existing is None
        machine = store.add_or_update(ip=ip, hostname=hostname, mac=mac, method=method)

        if is_new:
            self.console.after(0, lambda m=machine: self.console.success(
                f"{m.ip:<20} {m.hostname:<20} [{', '.join(m.methods)}]"
            ))
            threading.Thread(target=self._identify, args=(machine,), daemon=True).start()

    def _identify(self, machine):
        result = identify_device(machine.ip)
        if result:
            machine.device_type = result
            self.console.after(0, lambda m=machine: self.console.info(
                f"  {m.ip:<20} identified as: {m.device_type}"
            ))

    def _cmd_exit(self, args):
        self.destroy()

    def _on_close(self):
        if self._passive_scanner:
            self._passive_scanner.stop()
        if self._active_scanner:
            self._active_scanner.stop()
        self.destroy()
