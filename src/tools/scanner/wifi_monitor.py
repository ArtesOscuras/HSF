import os
import re
import shutil
import subprocess
import threading
import time
from functools import partial

from scapy.all import sniff, Dot11, Dot11Beacon, Dot11Elt, RadioTap, NoPayload, wrpcap
from scapy.layers.eap import EAPOL, EAPOL_KEY
from scapy.config import conf

conf.verb = 0

CHANNELS_24 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
CHANNELS_5 = [36, 40, 44, 48, 149, 153, 157, 161, 165]
CHANNELS = CHANNELS_24 + CHANNELS_5

DWELL = 0.6
STALE_AGE = 60.0
HANDSHAKE_HOLD = 3.0

_lock = threading.Lock()
_mode_lock = threading.RLock()
_networks = {}
_probes = {}

_beacon_count = 0
_probe_count = 0
_data_count = 0
_other_count = 0

_known_bssids = set()

_handshake_frames = {}
_handshake_state = {}
_handshake_count = 0
_hold_until = {}

_hash_registered = set()

_locked_channel = None

_scanner = None
_last_error = ""

_BROADCAST = "FF:FF:FF:FF:FF:FF"


def _which(name):
    return shutil.which(name) is not None


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired):
        return False, "", ""


def _mac(v):
    return str(v).upper() if v else ""


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _is_mgmt(pkt):
    try:
        d = pkt[Dot11]
        return (d.type == 0 and d.subtype in (8, 4)) or d.type == 2
    except Exception:
        return False


def wifi_interfaces():
    if _which("nmcli"):
        ok, out, _ = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
        if ok:
            names = []
            for line in out.splitlines():
                parts = _split_terse(line)
                if len(parts) >= 2 and parts[1] == "wifi":
                    names.append(parts[0])
            if names:
                return names
    if _which("iw"):
        ok, out, _ = _run(["iw", "dev"])
        if ok:
            names = []
            for line in out.splitlines():
                m = re.match(r"\s*Interface\s+(\S+)", line)
                if m:
                    names.append(m.group(1))
            if names:
                return names
    return []


def wifi_interfaces_state():
    if not _which("nmcli"):
        return []
    ok, out, _ = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
    if not ok:
        return []
    result = []
    for line in out.splitlines():
        parts = _split_terse(line)
        if len(parts) >= 3 and parts[1] == "wifi":
            result.append((parts[0], parts[2]))
    return result


def _split_terse(line):
    return [p.replace("\\:", ":").replace("\\\\", "\\")
            for p in re.split(r"(?<!\\):", line)]


def _ssid(pkt):
    cur = pkt
    while cur is not None and not isinstance(cur, NoPayload):
        if isinstance(cur, Dot11Elt) and cur.ID == 0:
            info = cur.info
            if isinstance(info, bytes):
                return info.decode(errors="replace")
            return str(info or "")
        cur = cur.payload
    return ""


def _channel(pkt):
    ds = None
    ht = None
    vht = None
    cur = pkt
    while cur is not None and not isinstance(cur, NoPayload):
        if isinstance(cur, Dot11Elt):
            if cur.ID == 3:
                info = getattr(cur, "info", None)
                if info:
                    ds = info[0]
            elif cur.ID == 61:
                info = getattr(cur, "info", None)
                if info:
                    ht = info[0]
            elif cur.ID == 192:
                op = getattr(cur, "VHT_Operation_Info", None)
                if op is not None:
                    vht = op.channel_center0
                else:
                    info = getattr(cur, "info", None)
                    if info and len(info) > 1:
                        vht = info[1]
        cur = cur.payload
    return ds or ht or vht or 0


def _signal(pkt):
    try:
        return pkt[RadioTap].dBm_AntSignal
    except Exception:
        return None


def _security(pkt):
    privacy = False
    try:
        privacy = bool(int(pkt[Dot11Beacon].cap) & 0x10)
    except Exception:
        pass

    rsn = False
    wpa1 = False
    has_sae = False
    has_wpa2_akm = False

    cur = pkt
    while cur is not None and not isinstance(cur, NoPayload):
        if isinstance(cur, Dot11Elt):
            if cur.ID == 48:
                rsn = True
                info = cur.info
                if isinstance(info, bytes) and len(info) >= 8:
                    try:
                        pc = int.from_bytes(info[6:8], "little")
                        akm_off = 8 + 4 * pc
                        if len(info) >= akm_off + 2:
                            ac = int.from_bytes(info[akm_off:akm_off + 2], "little")
                            for i in range(ac):
                                off = akm_off + 2 + 4 * i
                                if len(info) >= off + 4:
                                    suite = info[off:off + 4]
                                    if suite[:3] == b"\x00\x0f\xac":
                                        t = suite[3]
                                        if t in (0x08, 0x09):
                                            has_sae = True
                                        elif t in (0x01, 0x02, 0x03, 0x04, 0x05, 0x06):
                                            has_wpa2_akm = True
                    except Exception:
                        pass
            elif cur.ID == 221:
                info = cur.info
                if isinstance(info, bytes) and len(info) >= 4 and info[:4] == b"\x00\x50\xf2\x01":
                    wpa1 = True
        cur = cur.payload

    if not privacy and not rsn and not wpa1:
        return "OPEN"
    if rsn:
        if has_sae and has_wpa2_akm:
            return "WPA2 WPA3"
        if has_sae:
            return "WPA3"
        if wpa1:
            return "WPA1 WPA2"
        return "WPA2"
    if wpa1:
        return "WPA1"
    if privacy:
        return "WEP"
    return "OPEN"


def dbm_to_pct(dbm):
    if dbm is None:
        return 0
    return max(0, min(100, 2 * (dbm + 100)))


def channel_to_freq(ch):
    if ch is None:
        return ""
    if 1 <= ch <= 13:
        return f"{2412 + (ch - 1) * 5} MHz"
    if 36 <= ch <= 64:
        return f"{5180 + (ch - 36) * 5} MHz"
    if 100 <= ch <= 144:
        return f"{5500 + (ch - 100) * 5} MHz"
    if 149 <= ch <= 165:
        return f"{5745 + (ch - 149) * 5} MHz"
    return f"{ch}"


def _process(pkt, device=None):
    global _beacon_count, _probe_count, _data_count, _other_count
    if not pkt.haslayer(Dot11):
        return
    d = pkt[Dot11]
    now = time.time()

    if d.type == 0 and d.subtype == 8:
        _beacon_count += 1
        bssid = _mac(d.addr2) or _mac(d.addr3)
        if not bssid:
            return
        _known_bssids.add(bssid)
        dbm = _signal(pkt)
        with _lock:
            n = _networks.get(bssid)
            if n is None:
                n = _networks[bssid] = {
                    "ssid": _ssid(pkt) or "(hidden)",
                    "bssid": bssid,
                    "signal": dbm_to_pct(dbm),
                    "signal_dbm": dbm,
                    "security": _security(pkt),
                    "chan": _channel(pkt),
                    "freq": channel_to_freq(_channel(pkt)),
                    "devices": set(),
                }
            else:
                n["ssid"] = _ssid(pkt) or n.get("ssid", "(hidden)")
                n["signal"] = dbm_to_pct(dbm)
                n["signal_dbm"] = dbm
                n["security"] = _security(pkt)
                n["chan"] = _channel(pkt)
                n["freq"] = channel_to_freq(_channel(pkt))
            if device:
                n["devices"].add(device)
            n["last_seen"] = now

    elif d.type == 0 and d.subtype == 4:
        _probe_count += 1
        client = _mac(d.addr2)
        if not client:
            return
        ssid = _ssid(pkt)
        ra = _mac(d.addr1)
        with _lock:
            entry = _probes.setdefault(client, {
                "ssids": set(),
                "bssids": set(),
                "signal": None,
                "last_seen": now,
            })
            if ssid:
                entry["ssids"].add(ssid)
            if ra and ra != _BROADCAST:
                entry["bssids"].add(ra)
            entry["last_seen"] = now
            dbm = _signal(pkt)
            if dbm is not None:
                entry["signal"] = dbm

    elif d.type == 2:
        addr1 = _mac(d.addr1)
        addr2 = _mac(d.addr2)
        addr3 = _mac(d.addr3)
        client = None
        bssid = None
        if addr2 in _known_bssids:
            bssid, client = addr2, addr1
        elif addr1 in _known_bssids:
            bssid, client = addr1, addr2
        elif addr3 in _known_bssids:
            bssid = addr3
            client = addr1 if addr2 == addr3 else addr2
        if bssid and client and client != bssid and client != _BROADCAST:
            _data_count += 1
            if _is_eapol_key(pkt):
                _record_handshake(bssid, client, pkt, device)
            with _lock:
                entry = _probes.setdefault(client, {
                    "ssids": set(),
                    "bssids": set(),
                    "signal": None,
                    "last_seen": now,
                })
                entry["bssids"].add(bssid)
                entry["last_seen"] = now
        else:
            _other_count += 1
    else:
        _other_count += 1


def _is_eapol_key(pkt):
    try:
        return pkt.haslayer(EAPOL) and pkt[EAPOL].type == 3
    except Exception:
        return False


def _eapol_msg_number(pkt):
    try:
        return pkt[EAPOL_KEY].guess_key_number()
    except Exception:
        return 0


def _extract_eapol(pkt):
    try:
        key = pkt[EAPOL_KEY]
    except Exception:
        return None
    msg = key.guess_key_number()
    try:
        nonce = bytes(key.key_nonce) if key.key_nonce else b"\x00" * 32
    except Exception:
        nonce = b"\x00" * 32
    try:
        mic = bytes(key.key_mic) if key.key_mic else b"\x00" * 16
    except Exception:
        mic = b"\x00" * 16
    try:
        keyver = int(key.key_descriptor_type_version) & 7
    except Exception:
        keyver = 0
    eapol = b""
    eapol_len = 0
    try:
        raw_eapol = bytes(pkt[EAPOL])
        if len(raw_eapol) >= 97:
            eapol = raw_eapol[:81] + b"\x00" * 16 + raw_eapol[97:]
            eapol_len = len(raw_eapol)
    except Exception:
        pass
    return {
        "msg": msg,
        "nonce": nonce,
        "mic": mic,
        "keyver": keyver,
        "eapol": eapol,
        "eapol_len": eapol_len,
    }


def _record_handshake(bssid, client, pkt, device):
    global _handshake_count
    fields = _extract_eapol(pkt)
    msg = fields["msg"] if fields else _eapol_msg_number(pkt)
    to_notify = None
    with _lock:
        state = _handshake_state.setdefault(bssid, {}).setdefault(
            client, {"seen": set(), "notified": False,
                     "anonce": None, "snonce": None, "keymic": None,
                     "keyver": 0, "eapol": None, "eapol_len": 0})
        if msg:
            state["seen"].add(msg)
        if fields:
            if msg == 1 and not state.get("anonce"):
                state["anonce"] = fields["nonce"]
            elif msg == 2:
                state["snonce"] = fields["nonce"]
                state["keymic"] = fields["mic"]
                state["keyver"] = fields["keyver"]
                state["eapol"] = fields["eapol"]
                state["eapol_len"] = fields["eapol_len"]
            elif msg == 3 and not state.get("anonce"):
                state["anonce"] = fields["nonce"]
        state["last_seen"] = time.time()
        _handshake_frames.setdefault(bssid, []).append(pkt)
        complete = ((1 in state["seen"] and 2 in state["seen"])
                    or (2 in state["seen"] and 3 in state["seen"]))
        if complete and not state["notified"]:
            state["notified"] = True
            _handshake_count += 1
            ssid = _networks.get(bssid, {}).get("ssid", "")
            to_notify = (bssid, client, ssid)
    if device:
        _hold_until[device] = time.time() + HANDSHAKE_HOLD
    if to_notify:
        bssid, client, ssid = to_notify
        _write_handshake_pcap(bssid)
        _write_handshake_hc22000(bssid, client, ssid)
        _notify_handshake(bssid, client, ssid)


def _write_handshake_pcap(bssid):
    try:
        from src.hsf_paths import handshakes_dir, chown_to_real_user
    except Exception:
        return
    with _lock:
        frames = list(_handshake_frames.get(bssid, []))
        ssid = _networks.get(bssid, {}).get("ssid", "(hidden)")
    if not frames:
        return
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in ssid) or "hidden"
    name = f"{safe}_{bssid.replace(':', '')}.pcap"
    path = os.path.join(str(handshakes_dir()), name)
    try:
        wrpcap(path, frames)
        chown_to_real_user(path)
    except Exception as e:
        _emit_error(f"Could not write handshake pcap: {e}")


def _message_pair(seen):
    if 1 in seen and 2 in seen:
        return 128
    if 2 in seen and 3 in seen:
        return 130
    return 128


def _build_hc22000_line(ssid, bssid, client, anonce, keymic, eapol, message_pair):
    mic_hex = (keymic or b"\x00" * 16)[:16].hex()
    mac_ap = bssid.replace(":", "").lower()
    mac_sta = client.replace(":", "").lower()
    essid_hex = (ssid or "").encode("utf-8", errors="replace").hex()
    nonce_ap_hex = (anonce or b"\x00" * 32)[:32].hex()
    eapol_hex = (eapol or b"").hex()
    return (f"WPA*02*{mic_hex}*{mac_ap}*{mac_sta}*{essid_hex}"
            f"*{nonce_ap_hex}*{eapol_hex}*{message_pair:02x}\n")


def _write_handshake_hc22000(bssid, client, ssid):
    try:
        from src.hsf_paths import handshakes_dir, chown_to_real_user
    except Exception:
        return
    with _lock:
        state = _handshake_state.get(bssid, {}).get(client)
        if not state:
            return
        anonce = state.get("anonce")
        keymic = state.get("keymic")
        eapol = state.get("eapol")
        seen = set(state.get("seen", set()))
    if not (anonce and keymic and eapol):
        return
    line = _build_hc22000_line(ssid, bssid, client, anonce, keymic, eapol,
                               _message_pair(seen))
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in ssid) or "hidden"
    name = f"{safe}_{bssid.replace(':', '')}.hc22000"
    path = os.path.join(str(handshakes_dir()), name)
    try:
        with open(path, "a") as f:
            f.write(line)
        chown_to_real_user(path)
    except Exception as e:
        _emit_error(f"Could not write handshake hc22000: {e}")
        return
    _register_handshake_hash(bssid, path)


def _register_handshake_hash(bssid, path):
    if bssid in _hash_registered:
        return
    try:
        from src.machines import credential_db
        credential_db.save_hash_entry(
            "WPA handshake", path, hascat_mode="22000", origin="wifi monitor")
        _hash_registered.add(bssid)
    except Exception:
        pass


def _notify_handshake(bssid, client, ssid):
    try:
        from src import event_bus
        event_bus.submit({
            "type": "handshake",
            "message": f"WPA handshake captured for {ssid or '(hidden)'} ({bssid})",
            "ssid": ssid or "",
            "bssid": bssid,
            "client": client,
        })
    except Exception:
        pass


def flush_handshakes():
    with _lock:
        bssids = list(_handshake_frames)
    for bssid in bssids:
        _write_handshake_pcap(bssid)


def get_stats():
    with _lock:
        return {
            "networks": len(_networks),
            "probes": len(_probes),
            "handshakes": _handshake_count,
            "beacons_seen": _beacon_count,
            "probes_seen": _probe_count,
            "data_seen": _data_count,
            "other_seen": _other_count,
        }


def clear():
    global _beacon_count, _probe_count, _data_count, _other_count, _handshake_count
    with _lock:
        _networks.clear()
        _probes.clear()
        _handshake_frames.clear()
        _handshake_state.clear()
    _known_bssids.clear()
    _hash_registered.clear()
    _beacon_count = 0
    _probe_count = 0
    _data_count = 0
    _other_count = 0
    _handshake_count = 0
    unlock_channel()


def lock_channel(channel):
    global _locked_channel
    _locked_channel = channel


def unlock_channel():
    global _locked_channel
    _locked_channel = None


def is_locked():
    return _locked_channel is not None


def locked_channel():
    return _locked_channel


def get_networks(iface=None):
    now = time.time()
    result = []
    with _lock:
        for bssid, n in _networks.items():
            devices = sorted(n.get("devices") or set())
            if iface and iface not in devices:
                continue
            d = dict(n)
            d.pop("devices", None)
            d["devices"] = devices
            d["device"] = ", ".join(devices)
            d["stale"] = (now - n.get("last_seen", now)) > STALE_AGE
            result.append(d)
    result.sort(key=lambda x: -x["signal"])
    return result


def _scan_connected():
    now = time.time()
    for iface in wifi_interfaces():
        ok, out, _ = _run(["iw", "dev", iface, "link"])
        if not ok:
            continue
        bssid = ""
        ssid = ""
        freq = ""
        dbm = None
        for line in out.splitlines():
            m = re.match(r"Connected to\s+([0-9A-Fa-f:]{17})", line)
            if m:
                bssid = m.group(1).upper()
            m = re.search(r"SSID:\s*(.+)", line)
            if m:
                ssid = m.group(1).strip()
            m = re.search(r"freq:\s*([\d.]+)", line)
            if m:
                freq = m.group(1)
            m = re.search(r"signal:\s*(-?\d+)", line)
            if m:
                dbm = int(m.group(1))
        if not bssid:
            continue
        with _lock:
            n = _networks.get(bssid)
            if n is None:
                n = _networks[bssid] = {
                    "ssid": ssid or "(hidden)",
                    "bssid": bssid,
                    "signal": dbm_to_pct(dbm),
                    "signal_dbm": dbm,
                    "security": "OPEN",
                    "chan": 0,
                    "freq": f"{freq} MHz" if freq else "",
                    "devices": set(),
                }
            else:
                if ssid and n.get("ssid") == "(hidden)":
                    n["ssid"] = ssid
                if dbm is not None:
                    n["signal"] = max(n.get("signal", 0), dbm_to_pct(dbm))
                    n["signal_dbm"] = dbm
                if freq:
                    n["freq"] = f"{freq} MHz"
            n["devices"].add(iface)
            n["last_seen"] = now


def get_probes():
    now = time.time()
    result = []
    with _lock:
        for mac, e in _probes.items():
            result.append(_probe_dict(mac, e, now))
    result.sort(key=lambda x: x["last_seen"], reverse=True)
    return result


def probes_for(ssid=None, bssid=None):
    now = time.time()
    result = []
    with _lock:
        for mac, e in _probes.items():
            if ssid and ssid in e["ssids"]:
                result.append(_probe_dict(mac, e, now))
                continue
            if bssid and bssid.upper() in e["bssids"]:
                result.append(_probe_dict(mac, e, now))
    result.sort(key=lambda x: x["last_seen"], reverse=True)
    return result


def _probe_dict(mac, e, now=None):
    if now is None:
        now = time.time()
    return {
        "mac": mac,
        "ssids": sorted(e["ssids"]),
        "bssids": sorted(e["bssids"]),
        "signal": e["signal"],
        "last_seen": e["last_seen"],
        "stale": (now - e["last_seen"]) > STALE_AGE,
    }


def _scan_nmcli(iface=None):
    cmd = ["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,SECURITY,CHAN,FREQ,DEVICE",
           "device", "wifi", "list"]
    if iface:
        cmd += ["ifname", iface]
    ok, out, _ = _run(cmd, timeout=10)
    if not ok:
        return []
    nets = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = _split_terse(line)
        if len(parts) < 7:
            continue
        ssid, bssid, signal, security, chan, freq, device = parts[:7]
        nets.append({
            "ssid": ssid or "(hidden)",
            "bssid": bssid or "",
            "signal": _to_int(signal),
            "signal_dbm": None,
            "security": security or "OPEN",
            "chan": _to_int(chan),
            "freq": freq or "",
            "device": device or "",
            "devices": [device] if device else [],
            "stale": False,
            "last_seen": time.time(),
        })
    return nets


def scan_networks_fallback(iface=None):
    nets = _scan_nmcli(iface)
    seen = set()
    result = []
    for n in nets:
        key = n["bssid"] or n["ssid"]
        if key in seen:
            continue
        seen.add(key)
        result.append(n)
    result.sort(key=lambda x: -x["signal"])
    return result


def _iface_type(iface):
    ok, out, _ = _run(["iw", "dev", iface, "info"])
    if not ok:
        return ""
    for line in out.splitlines():
        m = re.match(r"\s*type\s+(\S+)", line)
        if m:
            return m.group(1)
    return ""


def _enter_monitor(iface):
    with _mode_lock:
        _run(["nmcli", "device", "set", iface, "managed", "no"])
        _run(["ip", "link", "set", iface, "down"])
        ok, _, err = _run(["iw", "dev", iface, "set", "type", "monitor"])
        _run(["ip", "link", "set", iface, "up"])
        time.sleep(0.4)
        if not ok:
            if _iface_type(iface) == "monitor":
                return True
            reason = err.strip() or "unknown error"
            _emit_error(
                f"Could not set {iface} to monitor mode: {reason}. "
                "WiFi monitor requires root (CAP_NET_ADMIN/CAP_NET_RAW). "
                "Falling back to system network scan (no client probes).")
            _exit_monitor(iface)
            return False
        return True


def _exit_monitor(iface):
    with _mode_lock:
        _run(["ip", "link", "set", iface, "down"])
        for _ in range(3):
            ok, _, _ = _run(["iw", "dev", iface, "set", "type", "managed"])
            if ok:
                break
            time.sleep(0.3)
        _run(["ip", "link", "set", iface, "up"])
        _run(["nmcli", "device", "set", iface, "managed", "yes"])


def _set_channel(iface, channel):
    if channel:
        _run(["iw", "dev", iface, "set", "channel", str(channel)])


class WifiMonitorService:
    def __init__(self):
        self._thread = None
        self._running = False
        self._ifaces = []
        self._workers = {}
        self._lock = threading.Lock()

    def start(self, iface=None):
        if self._running:
            return True
        self._running = True
        self._thread = threading.Thread(target=self._manager, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False

    @property
    def is_running(self):
        return self._running

    @property
    def iface(self):
        return ", ".join(self._ifaces) if self._ifaces else ""

    @property
    def ifaces(self):
        return list(self._ifaces)

    def _manager(self):
        while self._running:
            free = [n for n, s in wifi_interfaces_state() if s != "connected"]
            with self._lock:
                for iface in list(self._workers):
                    if iface not in free:
                        self._workers[iface]["stop"].set()
                        del self._workers[iface]
                for iface in free:
                    if iface not in self._workers:
                        stop_event = threading.Event()
                        self._workers[iface] = {"stop": stop_event}
                        threading.Thread(
                            target=self._worker,
                            args=(iface, stop_event),
                            daemon=True,
                        ).start()
                self._ifaces = sorted(self._workers)
            if self._running:
                _scan_connected()
            time.sleep(5)

    def _worker(self, iface, stop_event):
        if not _enter_monitor(iface):
            return
        try:
            self._hop_loop(iface, stop_event)
        finally:
            _exit_monitor(iface)

    def _hop_loop(self, iface, stop_event):
        last_err = 0.0
        process = partial(_process, device=iface)
        locked_set = None
        while self._running and not stop_event.is_set():
            locked = _locked_channel
            if locked:
                if locked_set != locked:
                    _set_channel(iface, locked)
                    locked_set = locked
                last_err = self._sniff_dwell(iface, process, last_err)
            else:
                locked_set = None
                for ch in CHANNELS:
                    if stop_event.is_set() or not self._running:
                        break
                    _set_channel(iface, ch)
                    last_err = self._sniff_dwell(iface, process, last_err)
                    while (self._running and not stop_event.is_set()
                           and _hold_until.get(iface, 0) > time.time()):
                        last_err = self._sniff_dwell(iface, process, last_err)

    def _sniff_dwell(self, iface, process, last_err):
        try:
            sniff(iface=iface, prn=process, lfilter=_is_mgmt,
                  timeout=DWELL, store=0)
        except OSError as e:
            now = time.time()
            if now - last_err > 5:
                _emit_error(f"WiFi monitor error: {e}")
                last_err = now
            time.sleep(0.3)
        except Exception as e:
            now = time.time()
            if now - last_err > 5:
                _emit_error(f"WiFi monitor transient error: {e}")
                last_err = now
            time.sleep(0.3)
        return last_err


def _emit_error(msg):
    global _last_error
    _last_error = msg
    try:
        from src import event_bus
        event_bus.submit({"type": "scan_error", "message": msg})
    except Exception:
        pass


def get_service():
    global _scanner
    if _scanner is None:
        _scanner = WifiMonitorService()
    return _scanner


def start_monitor(iface=None):
    return get_service().start(iface)


def stop_monitor():
    if _scanner is not None:
        _scanner.stop()


def is_running():
    return _scanner is not None and _scanner.is_running


def last_error():
    return _last_error


def _monitor_interfaces():
    ok, out, _ = _run(["iw", "dev"])
    if not ok:
        return []
    result = []
    current = None
    for line in out.splitlines():
        m = re.match(r"\s*Interface\s+(\S+)", line)
        if m:
            current = m.group(1)
            continue
        if current is not None and "type monitor" in line:
            result.append(current)
            current = None
    return result


def recover_monitor_interfaces():
    for iface in _monitor_interfaces():
        _exit_monitor(iface)


def shutdown():
    if _scanner is not None:
        _scanner.stop()
    flush_handshakes()
    for iface in _monitor_interfaces():
        _exit_monitor(iface)
    for iface in wifi_interfaces():
        _run(["nmcli", "device", "set", iface, "managed", "yes"])
