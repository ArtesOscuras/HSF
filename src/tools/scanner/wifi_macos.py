"""macOS Wi-Fi scanning backend based on CoreWLAN (pyobjc).

This module is imported lazily and only ever used when HSF runs on macOS.
It provides the same normalized network dictionaries as the Linux backend so
the GUI can render them without platform-specific code.

Importing CoreWLAN is optional: if the dependency is missing, `available()`
returns False and the caller degrades gracefully. Nothing here is imported on
Linux, so the Linux code path is completely unaffected.
"""

import subprocess
import time


def available():
    try:
        import CoreWLAN  # noqa: F401
        return True
    except Exception:
        return False


def _client():
    from CoreWLAN import CWWiFiClient
    return CWWiFiClient.sharedWiFiClient()


def interfaces():
    if available():
        try:
            return [i.interfaceName() for i in _client().interfaces()]
        except Exception:
            pass
    fallback = _hardwareport_interface()
    return [fallback] if fallback else []


def _hardwareport_interface():
    try:
        r = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    port = None
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("Hardware Port:"):
            port = line.split(":", 1)[1].strip()
        elif line.startswith("Device:") and port and "Wi-Fi" in port:
            return line.split(":", 1)[1].strip()
    return None


def _dbm_to_pct(dbm):
    if dbm is None:
        return 0
    return max(0, min(100, 2 * (dbm + 100)))


def _channel_to_freq(ch):
    if ch in (None, 0):
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


_SECURITY_NAMES = {
    "kCWSecurityNone": "OPEN",
    "kCWSecurityWEP": "WEP",
    "kCWSecurityDynamicWEP": "WEP",
    "kCWSecurityWPAPersonal": "WPA1",
    "kCWSecurityWPAEnterprise": "WPA1",
    "kCWSecurityWPAPersonalMixed": "WPA1 WPA2",
    "kCWSecurityWPAEnterpriseMixed": "WPA1 WPA2",
    "kCWSecurityWPA2Personal": "WPA2",
    "kCWSecurityPersonal": "WPA2",
    "kCWSecurityWPA2Enterprise": "WPA2",
    "kCWSecurityEnterprise": "WPA2",
    "kCWSecurityWPA3Personal": "WPA3",
    "kCWSecurityWPA3Enterprise": "WPA3",
    "kCWSecurityWPA3Transition": "WPA2 WPA3",
    "kCWSecurityOWE": "OWE",
    "kCWSecurityOWETransition": "OWE",
}


def _security_label(corewlan, network):
    try:
        value = int(network.strongestSupportedSecurity())
    except Exception:
        return "WPA2"
    for name, label in _SECURITY_NAMES.items():
        if getattr(corewlan, name, None) == value:
            return label
    return "WPA2"


def scan(iface=None):
    if not available():
        return []
    import CoreWLAN

    client = _client()
    if iface:
        try:
            devices = [client.interfaceWithName_(iface)]
        except Exception:
            devices = []
    else:
        try:
            devices = list(client.interfaces())
        except Exception:
            devices = []

    nets = []
    for dev in devices:
        if dev is None:
            continue
        name = dev.interfaceName()
        try:
            networks, _err = dev.scanForNetworksWithName_error_(None, None)
        except Exception:
            continue
        for n in networks or []:
            bssid = (n.bssid() or "").upper()
            ssid = n.ssid() or "(hidden)"
            try:
                dbm = int(n.rssiValue())
            except (TypeError, ValueError):
                dbm = None
            try:
                chan = int(n.wlanChannel().channelNumber()) if n.wlanChannel() else 0
            except Exception:
                chan = 0
            nets.append({
                "ssid": ssid,
                "bssid": bssid,
                "signal": _dbm_to_pct(dbm),
                "signal_dbm": dbm,
                "security": _security_label(CoreWLAN, n),
                "chan": chan,
                "freq": _channel_to_freq(chan),
                "device": name,
                "devices": [name],
                "stale": False,
                "last_seen": time.time(),
            })
    return nets
