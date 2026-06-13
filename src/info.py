_checks = {}


def set(key, value):
    _checks[key] = value


def get(key, default=None):
    return _checks.get(key, default)


def all_checks():
    return dict(_checks)
