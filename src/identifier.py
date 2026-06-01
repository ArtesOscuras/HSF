import threading
import netifaces
from scapy.all import IP, ICMP, TCP, sr1, RandShort


TIMEOUT = 3
_sr1_lock = threading.Lock()
PORT_445 = 445
PORT_631 = 631
PORT_9100 = 9100
TTL_MIN = 120
TTL_MAX = 130


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


def identify_device(ip, gateway_ip=None, hostname=""):
    ttl = _probe_ttl(ip)

    if ttl == 255 and gateway_ip and ip == gateway_ip:
        return "Router"

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

    return "device unknown"
