import os
import sys
import tkinter as tk
import tkinter.font as tkfont

_FAMILY = None
_FAMILY_BOLD = None


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


def register_before_tk():
    global _FAMILY, _FAMILY_BOLD
    if _FAMILY is not None:
        return
    if sys.platform != "darwin":
        return
    base = os.path.join(os.path.dirname(__file__), "..", "..", "fonts")
    regular = os.path.join(base, "JetBrainsMonoNL-Regular.ttf")
    bold = os.path.join(base, "JetBrainsMonoNL-Bold.ttf")
    if os.path.isfile(regular):
        _register_font_macos(regular)
    if os.path.isfile(bold):
        _register_font_macos(bold)


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
    bold = os.path.join(base, "JetBrainsMonoNL-Bold.ttf")

    if sys.platform == "darwin":
        families = tkfont.families()
        for name in ("JetBrains Mono NL", "JetBrains Mono", "JetBrainsMonoNL"):
            if name in families:
                _set(name)
                return
        _set("Menlo")
        return

    if not os.path.isfile(regular):
        _set("Menlo")
        return

    try:
        root.tk.call("font", "create", "HSF-Font", "-file", regular)
        _FAMILY = "HSF-Font"
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
