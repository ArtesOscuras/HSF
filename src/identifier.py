from scapy.all import IP, TCP, sr1


PORT = 445
TTL_MIN = 120
TTL_MAX = 130
TIMEOUT = 3


def _probe_port_ttl(ip):
    pkt = IP(dst=ip) / TCP(dport=PORT, flags="S")
    reply = sr1(pkt, timeout=TIMEOUT, verbose=0)
    if reply is None:
        return None
    ttl = reply[IP].ttl
    if reply.haslayer(TCP):
        flags = reply[TCP].flags
        if flags & 0x12:
            return {"open": True, "ttl": ttl}
        return {"open": False, "ttl": ttl}
    return {"open": False, "ttl": ttl}


def identify_device(ip):
    result = _probe_port_ttl(ip)
    if result is None:
        return "device unknown"
    if TTL_MIN <= result["ttl"] <= TTL_MAX and result["open"]:
        return "Windows machine"
    return "device unknown"
