"""Cross-platform discovery of installed Chromium-family browsers.

GUI-free so it can be imported from background threads (e.g. the LLM agent's
daemon thread) without pulling in tkinter.
"""

import os
import shutil

_BROWSERS = {
    "google-chrome": ("Google Chrome", [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    ]),
    "google-chrome-stable": ("Google Chrome", []),
    "chromium": ("Chromium", [
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "C:\\Program Files\\Chromium\\Application\\chrome.exe",
    ]),
    "chromium-browser": ("Chromium", []),
    "brave-browser": ("Brave", [
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
    ]),
    "brave": ("Brave", []),
    "microsoft-edge": ("Microsoft Edge", [
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    ]),
    "edge": ("Microsoft Edge", []),
}


def _find_in_known_paths(extra_paths):
    for p in extra_paths:
        if os.path.isfile(p):
            return p
    return None


def find_browsers():
    found = {}
    seen = set()
    for binary, (label, extra_paths) in _BROWSERS.items():
        path = shutil.which(binary)
        if not path and extra_paths:
            path = _find_in_known_paths(extra_paths)
        if path and label not in seen:
            found[path] = label
            seen.add(label)
    return found
