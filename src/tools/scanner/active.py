import os
import time
import socket
import threading
import shutil
import ipaddress
from concurrent.futures import ThreadPoolExecutor
import netifaces
from scapy.all import ARP, Ether, srp
from zeroconf import Zeroconf, ServiceBrowser, BadTypeInNameException
from .mdns_cache import add_service, decode_properties

try:
    import nmap
    HAS_PYTHON_NMAP = True
except ImportError:
    HAS_PYTHON_NMAP = False

HAS_NMAP_BIN = shutil.which("nmap") is not None
HAS_NMAP = HAS_PYTHON_NMAP and HAS_NMAP_BIN

SERVICE_ENUM_TIME = 3
ACTIVE_INTERVAL = 5
THREADS = 20


class _ServiceTypeListener:
    def __init__(self):
        self.types = set()

    def add_service(self, zc, type_, name):
        self.types.add(name)

    def remove_service(self, *args):
        pass

    def update_service(self, *args):
        pass


class _ActiveServiceListener:
    def __init__(self, callback):
        self.callback = callback

    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name, timeout=2000)
        if not info:
            return
        hostname = info.server.rstrip(".")
        txt = decode_properties(info.properties)
        for addr in info.addresses:
            if len(addr) == 4:
                ip = socket.inet_ntoa(addr)
                if ip == "127.0.0.1":
                    continue
                add_service(ip, type_, hostname=hostname, txt=txt)
                self.callback(ip=ip, hostname=hostname, mac="", method="mDNS-Active")
            elif len(addr) == 16:
                ip = socket.inet_ntop(socket.AF_INET6, addr)
                if ip == "::1":
                    continue
                add_service(ip, type_, hostname=hostname, txt=txt)
                self.callback(ip=ip, hostname=hostname, mac="", method="mDNSv6-Active")

    def remove_service(self, *args):
        pass

    def update_service(self, *args):
        pass


class ActiveScanner:
    def __init__(self, on_host_callback, interface_name=None):
        self.on_host = on_host_callback
        self._zc = None
        self._threads = []
        self._running = False
        self._interface = None
        self._network = None
        self._preferred_iface = interface_name

    def start(self):
        if self._running:
            return
        self._running = True

        iface = self._resolve_interface()
        if not iface:
            raise RuntimeError("No active network interface found")

        self._interface = iface
        iface_name, ip, netmask = iface
        cidr_len = sum(bin(int(o)).count("1") for o in netmask.split("."))
        self._network = ipaddress.ip_network(f"{ip}/{cidr_len}", strict=False)

        self.on_host(ip=ip, hostname=socket.gethostname(), mac="", method="local")
        self.on_host(ip="127.0.0.1", hostname="localhost", mac="", method="local")

        t_arp = threading.Thread(target=self._run_arp, daemon=True)
        t_arp.start()
        self._threads.append(t_arp)

        self._zc = Zeroconf()
        t_mdns_active = threading.Thread(target=self._run_mdns_active, daemon=True)
        t_mdns_active.start()
        self._threads.append(t_mdns_active)

        if HAS_NMAP:
            t_nmap = threading.Thread(target=self._run_nmap, daemon=True)
            t_nmap.start()
            self._threads.append(t_nmap)

    def _resolve_interface(self):
        if self._preferred_iface:
            addrs = netifaces.ifaddresses(self._preferred_iface).get(netifaces.AF_INET)
            if addrs:
                return (self._preferred_iface, addrs[0]["addr"], addrs[0]["netmask"])
            raise RuntimeError(f"Interface '{self._preferred_iface}' not found or has no IPv4")
        return self._detect_interface()

    def _detect_interface(self):
        for iface in netifaces.interfaces():
            if iface == "lo0":
                continue
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET)
            if addrs:
                return (iface, addrs[0]["addr"], addrs[0]["netmask"])
        return None

    def _run_arp(self):
        network_str = str(self._network)
        while self._running:
            pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=network_str)
            try:
                ans, _ = srp(pkt, iface=self._interface[0], timeout=3, verbose=0)
                for _, r in ans:
                    self.on_host(ip=r.psrc, hostname="", mac=r.hwsrc, method="ARP")
            except PermissionError:
                self.on_host(ip="ERROR", hostname="ARP requires root privileges", mac="", method="error")
                return
            time.sleep(ACTIVE_INTERVAL)

    def _run_mdns_active(self):
        while self._running:
            tl = _ServiceTypeListener()
            ServiceBrowser(self._zc, "_services._dns-sd._udp.local.", tl)
            time.sleep(SERVICE_ENUM_TIME)
            for t in tl.types:
                if not self._running:
                    return
                ServiceBrowser(self._zc, t, _ActiveServiceListener(self.on_host))
            time.sleep(ACTIVE_INTERVAL)

    def _run_nmap(self):
        if not HAS_NMAP:
            return
        targets = [str(ip) for ip in self._network.hosts()]
        while self._running:
            with ThreadPoolExecutor(max_workers=THREADS) as exe:
                for ip in targets:
                    if not self._running:
                        return
                    exe.submit(self._nmap_scan, ip)
            time.sleep(ACTIVE_INTERVAL)

    def _nmap_scan(self, ip):
        try:
            nm = nmap.PortScanner()
            nm.scan(hosts=ip, arguments="-sU -Pn -p 5353 --open")
            if ip not in nm.all_hosts():
                return
            if 5353 not in nm[ip].get("udp", {}):
                return
            mac = nm[ip]["addresses"].get("mac", "")
            hostname = ""
            if nm[ip]["hostnames"]:
                hostname = nm[ip]["hostnames"][0].get("name", "")
            if not hostname and mac:
                vendor = nm[ip].get("ven", {}).get(mac)
                if vendor:
                    hostname = f"{vendor} (ven)"
            self.on_host(ip=ip, hostname=hostname, mac=mac, method="Nmap-Active")
        except Exception:
            pass

    def stop(self):
        self._running = False
        if self._zc:
            self._zc.close()

    @property
    def is_running(self):
        return self._running

    @property
    def has_nmap(self):
        return HAS_NMAP

    @property
    def interface_name(self):
        return self._interface[0] if self._interface else ""

    @property
    def interface_ip(self):
        return self._interface[1] if self._interface else ""

    @property
    def network_cidr(self):
        return str(self._network) if self._network else ""
