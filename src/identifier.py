from concurrent.futures import ThreadPoolExecutor
import os
import time as _time
import netifaces
from scapy.all import IP, ICMP, TCP, UDP, DNS, DNSQR, sr1, RandShort


# --- debug logging -----------------------------------------------------------
_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DBG_FILE = os.path.join(_proj_root, "databases", "debugging_logs")
_DBG_LOCK = __import__("threading").Lock()


def _dbg(msg):
    line = f"{_time.strftime('%H:%M:%S')}  {msg}\n"
    with _DBG_LOCK:
        os.makedirs(os.path.dirname(_DBG_FILE), exist_ok=True)
        with open(_DBG_FILE, "a") as f:
            f.write(line)
# ---------------------------------------------------------------------------


TIMEOUT = 1.5
PORT_445 = 445
PORT_631 = 631
PORT_9100 = 9100
PORT_MDNS = 5353
PORT_RTSP = 554
PORT_ONVIF_DISCOVERY = 3702
TTL_ROUTER_MIN = 250
TTL_ROUTER_MAX = 256
TTL_WIN_MIN = 120
TTL_WIN_MAX = 130
SERVICE_APPLE_MOBDEV2 = "_apple-mobdev2._tcp.local."
SERVICE_COMPANION_LINK = "_companion-link._tcp.local."
SERVICE_RDLINK = "_rdlink._tcp.local."
SERVICE_APPLETV = "_appletv-v2._tcp.local."
SERVICE_HOMEKIT = "_homekit._tcp.local."
SERVICE_RFB = "_rfb._tcp.local."
SERVICE_AIRPLAY = "_airplay._tcp.local."
SERVICE_RAOP = "_raop._tcp.local."
SERVICE_GOOGLECAST = "_googlecast._tcp.local."
SERVICE_ONVIF = "_onvif._tcp.local."
SERVICE_RTSP = "_rtsp._tcp.local."

MAC_HOSTNAME_KEYWORDS = (
    "macbook", "imac", "macmini", "macpro", "mac studio", "mac",
)

ANDROID_KEYWORDS = (
    "android", "samsung", "xiaomi", "oneplus", "huawei",
    "google", "pixel", "oppo", "vivo", "realme",
    "motorola", "nokia", "sony", "lg", "htc",
    "lenovo", "honor", "asus", "meizu", "nothing",
    "fairphone", "infinix", "tecno", "zte", "alcatel",
    "blackberry", "xperia", "nexus", "redmi", "poco",
    "miui", "coloros",
)


def _probe_ttl(ip):
    reply = sr1(IP(dst=ip) / ICMP(), timeout=TIMEOUT, verbose=0)
    if reply is None:
        return None
    if reply[IP].src != ip:
        return None
    return reply[IP].ttl


def _probe_port(ip, port):
    sport = RandShort()
    pkt = IP(dst=ip) / TCP(sport=sport, dport=port, flags="S")
    reply = sr1(pkt, timeout=TIMEOUT, verbose=0)
    if reply is None:
        return None
    if reply[IP].src != ip or reply[TCP].dport != sport:
        return None
    ttl = reply[IP].ttl
    if reply.haslayer(TCP):
        flags = reply[TCP].flags
        if flags & 0x12:
            return {"open": True, "ttl": ttl}
        return {"open": False, "ttl": ttl}
    return {"open": False, "ttl": ttl}


def _probe_mdns_service(ip, service_name):
    from src.scanner.mdns_cache import has_service, add_service as cache_add

    cached = has_service(ip, service_name)
    if cached:
        return True

    _dbg(f"  [active-mdns] probing {ip} for {service_name}")
    pkt = IP(dst=ip) / UDP(sport=RandShort(), dport=PORT_MDNS) / DNS(rd=1, qd=DNSQR(qname=service_name, qtype="PTR"))
    reply = sr1(pkt, timeout=TIMEOUT, verbose=0)
    if reply is None:
        _dbg(f"  [active-mdns] {service_name} -> no reply")
        return False
    if reply[IP].src != ip:
        _dbg(f"  [active-mdns] {service_name} -> src mismatch")
        return False
    found = reply.haslayer(DNS) and reply[DNS].ancount > 0
    _dbg(f"  [active-mdns] {service_name} -> found={found}")
    if found:
        cache_add(ip, service_name)
    return found


def _probe_udp_port(ip, port):
    pkt = IP(dst=ip) / UDP(sport=RandShort(), dport=port)
    reply = sr1(pkt, timeout=TIMEOUT, verbose=0)
    if reply is None:
        return True
    if reply.haslayer(ICMP) and reply[ICMP].type == 3 and reply[ICMP].code == 3:
        return False
    return True


def get_gateway_ip():
    try:
        return netifaces.gateways()["default"][netifaces.AF_INET][0]
    except (KeyError, IndexError):
        return None


class ProbeContext:
    """Lazy cache for network probes so each probe runs at most once per device."""

    def __init__(self, ip):
        self.ip = ip
        self._ttl = None
        self._ttl_queried = False
        self._ports = {}
        self._udp_ports = {}
        self._mdns_services = {}
        self._mdns_txt_records = {}

    def ttl(self):
        if not self._ttl_queried:
            self._ttl = _probe_ttl(self.ip)
            self._ttl_queried = True
        return self._ttl

    def port(self, port):
        if port not in self._ports:
            self._ports[port] = _probe_port(self.ip, port)
        return self._ports[port]

    def udp_port(self, port):
        if port not in self._udp_ports:
            self._udp_ports[port] = _probe_udp_port(self.ip, port)
        return self._udp_ports[port]

    def mdns_service(self, service_name):
        if service_name not in self._mdns_services:
            self._mdns_services[service_name] = _probe_mdns_service(self.ip, service_name)
        return self._mdns_services[service_name]

    def mdns_txt(self, service_name):
        if service_name not in self._mdns_txt_records:
            from src.scanner.mdns_cache import get_txt
            txt = get_txt(self.ip, service_name)
            if txt:
                self._mdns_txt_records[service_name] = txt
            else:
                self._mdns_txt_records[service_name] = self._resolve_mdns_txt(service_name)
        return self._mdns_txt_records[service_name]

    def _resolve_mdns_txt(self, service_name):
        import socket
        import threading as _th
        from zeroconf import Zeroconf, ServiceBrowser
        from src.scanner.mdns_cache import add_service, decode_properties

        zc = Zeroconf()
        result = {}
        done = _th.Event()

        class _Resolver:
            def add_service(self_, _zc, _type, _name):
                try:
                    info = _zc.get_service_info(_type, _name, timeout=2000)
                    if not info:
                        return
                    for addr in info.addresses:
                        if len(addr) == 4 and socket.inet_ntoa(addr) == self.ip:
                            result.update(decode_properties(info.properties))
                            done.set()
                except Exception:
                    pass

            def remove_service(self_, *args):
                pass

            def update_service(self_, *args):
                pass

        ServiceBrowser(zc, service_name, _Resolver())
        done.wait(timeout=2.5)
        zc.close()

        if result:
            add_service(self.ip, service_name, txt=result)
        return result

    def mdns_all_services(self):
        from src.scanner.mdns_cache import get_services
        return get_services(self.ip)

    def warmup(self):
        services = (
            SERVICE_RDLINK, SERVICE_APPLE_MOBDEV2, SERVICE_COMPANION_LINK,
            SERVICE_APPLETV, SERVICE_HOMEKIT, SERVICE_GOOGLECAST,
            SERVICE_ONVIF, SERVICE_RTSP, SERVICE_AIRPLAY, SERVICE_RAOP,
        )
        ports = (PORT_445, PORT_9100, PORT_631, PORT_RTSP)
        udp_ports = (PORT_ONVIF_DISCOVERY,)

        def _do_ttl():
            self._ttl = _probe_ttl(self.ip)
            self._ttl_queried = True

        def _do_mdns(svc):
            self._mdns_services[svc] = _probe_mdns_service(self.ip, svc)

        def _do_port(p):
            self._ports[p] = _probe_port(self.ip, p)

        def _do_udp(p):
            self._udp_ports[p] = _probe_udp_port(self.ip, p)

        with ThreadPoolExecutor(max_workers=16) as exe:
            exe.submit(_do_ttl)
            for svc in services:
                exe.submit(_do_mdns, svc)
            for p in ports:
                exe.submit(_do_port, p)
            for p in udp_ports:
                exe.submit(_do_udp, p)

        # --- debug dump ---
        found_services = [s for s, v in self._mdns_services.items() if v]
        open_ports = [str(p) for p, r in self._ports.items() if r and r.get("open")]
        _dbg(f"IDENTIFY {self.ip}  hostname={self.ip}")
        _dbg(f"  ttl={self._ttl}")
        _dbg(f"  cached mDNS services={found_services}")
        _dbg(f"  open ports={open_ports}")
        from src.scanner.mdns_cache import get_services as _gs
        all_gs = _gs(self.ip)
        _dbg(f"  global cache services={sorted(all_gs.keys())}")
        for svc_name, svc_info in all_gs.items():
            txt_keys = sorted(svc_info.get("txt", {}).keys())
            _dbg(f"    {svc_name}  txt_keys={txt_keys}")


class BaseIdentifier:
    """Base class for device identifiers. Override ``identify``."""

    name = ""

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        raise NotImplementedError


class RouterIdentifier(BaseIdentifier):
    name = "router"

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        ttl = context.ttl()
        if ttl is None:
            return None
        if TTL_ROUTER_MIN <= ttl <= TTL_ROUTER_MAX and gateway_ip and ip == gateway_ip:
            return "Router"
        return None


class MacIdentifier(BaseIdentifier):
    name = "mac"

    def _extract_model(self, context):
        for service_name, info in context.mdns_all_services().items():
            model = info.get("txt", {}).get("model", "").strip()
            if model:
                return model
            am = info.get("txt", {}).get("am", "").strip()
            if am:
                return am
        return ""

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        if context.mdns_service(SERVICE_RDLINK):
            model = self._extract_model(context)
            if model:
                return f"Mac ({model})"
            return "Mac"

        has_cl = context.mdns_service(SERVICE_COMPANION_LINK)
        has_airplay = context.mdns_service(SERVICE_AIRPLAY)
        has_raop = context.mdns_service(SERVICE_RAOP)

        if not (has_cl or has_airplay or has_raop):
            return None

        model = self._extract_model(context)
        if model and model.lower().startswith("mac"):
            return f"Mac ({model})"

        txt_cl = context.mdns_txt(SERVICE_COMPANION_LINK)
        if txt_cl.get("osxvers", "").strip():
            return "Mac"

        return None


class IOSIdentifier(BaseIdentifier):
    name = "ios"

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        h = hostname.lower()

        has_apple = context.mdns_service(SERVICE_APPLE_MOBDEV2)
        has_apple |= context.mdns_service(SERVICE_COMPANION_LINK)
        has_apple |= context.mdns_service(SERVICE_APPLETV)
        has_apple |= context.mdns_service(SERVICE_HOMEKIT)
        has_apple |= context.mdns_service(SERVICE_AIRPLAY)
        has_apple |= context.mdns_service(SERVICE_RAOP)

        if has_apple:
            if "ipad" in h:
                return "iPad"
            if "iphone" in h:
                return "iPhone"
            return "iOS device"
        return None


class AndroidIdentifier(BaseIdentifier):
    name = "android"

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        if context.mdns_service(SERVICE_GOOGLECAST):
            hostname_lower = hostname.lower()
            if any(kw in hostname_lower for kw in ANDROID_KEYWORDS):
                return "Android device"
        return None


class WindowsIdentifier(BaseIdentifier):
    name = "windows"

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        ttl = context.ttl()
        if ttl is None:
            return None
        if TTL_WIN_MIN <= ttl <= TTL_WIN_MAX:
            result = context.port(PORT_445)
            if result and result["open"]:
                return "Windows machine"
        return None


class PrinterIdentifier(BaseIdentifier):
    name = "printer"

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        result_9100 = context.port(PORT_9100)
        if result_9100 and result_9100["open"]:
            return "Printer"

        if "printer" in hostname.lower():
            result_631 = context.port(PORT_631)
            if result_631 and result_631["open"]:
                return "Printer"
        return None


class IPCameraIdentifier(BaseIdentifier):
    name = "ip_camera"

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        camera_score = 0
        if context.udp_port(PORT_ONVIF_DISCOVERY):
            camera_score += 1
        rtsp_open = context.port(PORT_RTSP)
        if rtsp_open and rtsp_open["open"]:
            camera_score += 1
        if context.mdns_service(SERVICE_ONVIF):
            camera_score += 1
        if context.mdns_service(SERVICE_RTSP):
            camera_score += 1
        if camera_score >= 2:
            return "IP Camera"
        return None


class FallbackIdentifier(BaseIdentifier):
    name = "fallback"

    def identify(self, ip, context, gateway_ip=None, hostname=""):
        return "device unknown"


# ---------------------------------------------------------------------------
# Identifier registry — identifiers that run *before* the TTL-is-None gate
# (these evaluate regardless of whether the host responds to ICMP ping).
# ---------------------------------------------------------------------------
_pre_ttl_identifiers = []

# Identifiers that run *after* the TTL gate.
_post_ttl_identifiers = []


def _init_defaults():
    _pre_ttl_identifiers.extend([
        RouterIdentifier(),
        MacIdentifier(),
        IOSIdentifier(),
        AndroidIdentifier(),
    ])
    _post_ttl_identifiers.extend([
        WindowsIdentifier(),
        PrinterIdentifier(),
        IPCameraIdentifier(),
    ])


_init_defaults()


def register_identifier(identifier, before_ttl_gate=False):
    if before_ttl_gate:
        _pre_ttl_identifiers.append(identifier)
    else:
        _post_ttl_identifiers.append(identifier)


def unregister_identifier(identifier):
    lst = _pre_ttl_identifiers if identifier in _pre_ttl_identifiers else _post_ttl_identifiers
    lst.remove(identifier)


def get_identifiers():
    return list(_pre_ttl_identifiers) + list(_post_ttl_identifiers)


def identify_device(ip, gateway_ip=None, hostname=""):
    _dbg(f"")
    _dbg(f"=== IDENTIFY {ip}  hostname={hostname}  gateway={gateway_ip} ===")

    context = ProbeContext(ip)
    context.warmup()

    for identifier in _pre_ttl_identifiers:
        result = identifier.identify(ip, context, gateway_ip=gateway_ip, hostname=hostname)
        _dbg(f"  {identifier.name}: --> {result!r}")
        if result:
            _dbg(f"  FINAL: {result}")
            return result

    if context.ttl() is None:
        _dbg(f"  TTL gate: no ping response -> device unknown")
        return "device unknown"

    for identifier in _post_ttl_identifiers:
        result = identifier.identify(ip, context, gateway_ip=gateway_ip, hostname=hostname)
        _dbg(f"  {identifier.name}: --> {result!r}")
        if result:
            _dbg(f"  FINAL: {result}")
            return result

    _dbg(f"  FINAL: device unknown")
    return "device unknown"
