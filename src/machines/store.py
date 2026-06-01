from datetime import datetime


class Machine:
    def __init__(self, ip, hostname="", mac="", method=""):
        self.ip = ip
        self.hostname = hostname
        self.mac = mac
        self.device_type = ""
        self.methods = {method} if method else set()
        self.first_seen = datetime.now()
        self.last_seen = datetime.now()

    def update(self, hostname="", mac="", method=""):
        if hostname and not self.hostname:
            self.hostname = hostname
        if mac and not self.mac:
            self.mac = mac
        if method:
            self.methods.add(method)
        self.last_seen = datetime.now()

    def to_dict(self):
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "mac": self.mac,
            "device_type": self.device_type,
            "methods": sorted(self.methods),
            "first_seen": self.first_seen.strftime("%H:%M:%S"),
            "last_seen": self.last_seen.strftime("%H:%M:%S"),
        }


class MachineStore:
    def __init__(self):
        self._machines = {}

    def add_or_update(self, ip, hostname="", mac="", method=""):
        if ip in self._machines:
            self._machines[ip].update(hostname=hostname, mac=mac, method=method)
        else:
            self._machines[ip] = Machine(ip, hostname=hostname, mac=mac, method=method)
        return self._machines[ip]

    def get(self, ip):
        return self._machines.get(ip)

    def get_all(self):
        return list(self._machines.values())

    def get_all_sorted(self):
        return sorted(self._machines.values(), key=lambda m: m.first_seen)

    def count(self):
        return len(self._machines)

    def clear(self):
        self._machines.clear()
