import threading
import netifaces
from scapy.all import IP, ICMP, TCP, UDP, DNS, DNSQR, sr1, RandShort


TIMEOUT = 3
_sr1_lock = threading.Lock()
PORT_445 = 445
PORT_631 = 631
PORT_9100 = 9100
PORT_MDNS = 5353
PORT_RTSP = 554
PORT_ONVIF_DISCOVERY = 3702
TTL_MIN = 120
TTL_MAX = 130
SERVICE_APPLE_MOBDEV2 = "_apple-mobdev2._tcp.local."
SERVICE_COMPANION_LINK = "_companion-link._tcp.local."
SERVICE_GOOGLECAST = "_googlecast._tcp.local."
SERVICE_ONVIF = "_onvif._tcp.local."
SERVICE_RTSP = "_rtsp._tcp.local."

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
    with _sr1_lock:
        reply = sr1(IP(dst=ip) / ICMP(), timeout=TIMEOUT, verbose=0)
        if reply is None:
            return None
        if reply[IP].src != ip:
            return None
        return reply[IP].ttl


def _probe_port(ip, port):
    with _sr1_lock:
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


def get_gateway_ip():
    try:
        return netifaces.gateways()["default"][netifaces.AF_INET][0]
    except (KeyError, IndexError):
        return None


def _probe_mdns_service(ip, service_name):
    with _sr1_lock:
        pkt = IP(dst=ip) / UDP(sport=RandShort(), dport=PORT_MDNS) / DNS(rd=1, qd=DNSQR(qname=service_name, qtype="PTR"))
        reply = sr1(pkt, timeout=TIMEOUT, verbose=0)
        if reply is None:
            return False
        if reply[IP].src != ip:
            return False
        return reply.haslayer(DNS) and reply[DNS].ancount > 0


def _probe_udp_port(ip, port):
    with _sr1_lock:
        pkt = IP(dst=ip) / UDP(sport=RandShort(), dport=port)
        reply = sr1(pkt, timeout=TIMEOUT, verbose=0)
        if reply is None:
            return True
        if reply.haslayer(ICMP) and reply[ICMP].type == 3 and reply[ICMP].code == 3:
            return False
        return True


def identify_device(ip, gateway_ip=None, hostname=""):
    ttl = _probe_ttl(ip)

    if ttl == 255 and gateway_ip and ip == gateway_ip:
        return "Router"

    if _probe_mdns_service(ip, SERVICE_APPLE_MOBDEV2) or _probe_mdns_service(ip, SERVICE_COMPANION_LINK):
        if "ipad" in hostname.lower():
            return "iPad"
        if "iphone" in hostname.lower():
            return "iPhone"
        return "iOS device"

    if _probe_mdns_service(ip, SERVICE_GOOGLECAST):
        hostname_lower = hostname.lower()
        if any(kw in hostname_lower for kw in ANDROID_KEYWORDS):
            return "Android device"

    if ttl is None:
        return "device unknown"

    if TTL_MIN <= ttl <= TTL_MAX:
        result = _probe_port(ip, PORT_445)
        if result and result["open"]:
            return "Windows machine"

    result_9100 = _probe_port(ip, PORT_9100)
    if result_9100 and result_9100["open"]:
        return "Printer"

    if "printer" in hostname.lower():
        result_631 = _probe_port(ip, PORT_631)
        if result_631 and result_631["open"]:
            return "Printer"

    camera_score = 0
    if _probe_udp_port(ip, PORT_ONVIF_DISCOVERY):
        camera_score += 1
    rtsp_open = _probe_port(ip, PORT_RTSP)
    if rtsp_open and rtsp_open["open"]:
        camera_score += 1
    if _probe_mdns_service(ip, SERVICE_ONVIF):
        camera_score += 1
    if _probe_mdns_service(ip, SERVICE_RTSP):
        camera_score += 1
    if camera_score >= 2:
        return "IP Camera"

    return "device unknown"
