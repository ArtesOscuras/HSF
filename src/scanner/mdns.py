import socket
import threading
import time
from zeroconf import Zeroconf, ServiceBrowser, BadTypeInNameException


class _PassiveListener:
    def __init__(self, callback):
        self.callback = callback

    def add_service(self, zc, type_, name):
        try:
            info = zc.get_service_info(type_, name, timeout=1000)
            if not info:
                return
            hostname = info.server.rstrip(".")
            for addr in info.addresses:
                if len(addr) == 4:
                    self.callback(
                        ip=socket.inet_ntoa(addr),
                        hostname=hostname,
                        method="mDNS-Passive"
                    )
                elif len(addr) == 16:
                    self.callback(
                        ip=socket.inet_ntop(socket.AF_INET6, addr),
                        hostname=hostname,
                        method="mDNSv6-Passive"
                    )
        except BadTypeInNameException:
            pass

    def remove_service(self, *args):
        pass

    def update_service(self, *args):
        pass


class PassiveMDNSScanner:
    def __init__(self, on_host_callback):
        self.on_host = on_host_callback
        self._zc = None
        self._browser = None
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self._zc = Zeroconf()
        listener = _PassiveListener(self._on_host_discovered)
        self._browser = ServiceBrowser(self._zc, "_services._dns-sd._udp.local.", listener)
        try:
            while self._running:
                time.sleep(0.5)
        finally:
            self._zc.close()

    def _on_host_discovered(self, ip, hostname, method):
        self.on_host(ip, hostname, method)

    def stop(self):
        self._running = False
        if self._zc:
            self._zc.close()

    @property
    def is_running(self):
        return self._running
