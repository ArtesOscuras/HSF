import os
import shutil
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont

_FAMILY = None
_FAMILY_BOLD = None

_LINUX_FALLBACKS = ["DejaVu Sans Mono", "Liberation Mono", "Monospace"]


def _register_font_macos(path):
    import ctypes
    import ctypes.util
    try:
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        ct = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreText"))

        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFURLCreateWithFileSystemPath.restype = ctypes.c_void_p
        cf.CFURLCreateWithFileSystemPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_bool]
        cf.CFRelease.restype = None
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
        ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]

        path_cf = cf.CFStringCreateWithCString(None, path.encode("utf-8"), 0x08000100)
        if not path_cf:
            return False
        url = cf.CFURLCreateWithFileSystemPath(None, path_cf, 0, False)
        if not url:
            cf.CFRelease(path_cf)
            return False
        result = ct.CTFontManagerRegisterFontsForURL(url, 1, None)
        cf.CFRelease(url)
        cf.CFRelease(path_cf)
        return result
    except Exception:
        return False


def _install_font_linux(base, names):
    target = os.path.expanduser("~/.local/share/fonts")
    os.makedirs(target, exist_ok=True)
    copied = False
    for name in names:
        src = os.path.join(base, name)
        dst = os.path.join(target, name)
        if os.path.isfile(src) and not os.path.isfile(dst):
            try:
                shutil.copy2(src, dst)
                copied = True
            except (OSError, PermissionError):
                pass
    if copied:
        try:
            subprocess.run(["fc-cache", "-f"], timeout=10, capture_output=True)
        except Exception:
            pass


def register_before_tk():
    global _FAMILY, _FAMILY_BOLD
    if _FAMILY is not None:
        return
    base = os.path.join(os.path.dirname(__file__), "..", "..", "fonts")
    regular = os.path.join(base, "JetBrainsMonoNL-Regular.ttf")
    bold = os.path.join(base, "JetBrainsMonoNL-Bold.ttf")

    if sys.platform == "darwin":
        if os.path.isfile(regular):
            _register_font_macos(regular)
        if os.path.isfile(bold):
            _register_font_macos(bold)
    elif sys.platform.startswith("linux"):
        _install_font_linux(base, ["JetBrainsMonoNL-Regular.ttf", "JetBrainsMonoNL-Bold.ttf"])


def init(root):
    global _FAMILY, _FAMILY_BOLD
    if _FAMILY is not None:
        return

    families = tkfont.families()
    for name in ("JetBrains Mono NL", "JetBrains Mono", "JetBrainsMonoNL"):
        if name in families:
            _set(name)
            return

    base = os.path.join(os.path.dirname(__file__), "..", "..", "fonts")
    regular = os.path.join(base, "JetBrainsMonoNL-Regular.ttf")

    if sys.platform == "darwin":
        for name in ("JetBrains Mono NL", "JetBrains Mono", "JetBrainsMonoNL"):
            if name in tkfont.families():
                _set(name)
                return
        _set("Menlo")
        return

    if sys.platform.startswith("linux"):
        for fb in _LINUX_FALLBACKS:
            if fb in families:
                _set(fb)
                return
        _set("Monospace")
        return

    if not os.path.isfile(regular):
        _set("Menlo")
        return

    try:
        root.tk.call("font", "create", "HSF-Font", "-file", regular)
        _FAMILY = "HSF-Font"
        bold = os.path.join(base, "JetBrainsMonoNL-Bold.ttf")
        if os.path.isfile(bold):
            root.tk.call("font", "create", "HSF-Font-Bold", "-file", bold)
            _FAMILY_BOLD = "HSF-Font-Bold"
        else:
            _FAMILY_BOLD = "HSF-Font"
    except tk.TclError:
        _set("Menlo")


def _set(name):
    global _FAMILY, _FAMILY_BOLD
    _FAMILY = name
    _FAMILY_BOLD = name


def family():
    if _FAMILY is None:
        return "Menlo"
    return _FAMILY


def family_bold():
    if _FAMILY_BOLD is None:
        return "Menlo"
    return _FAMILY_BOLD
