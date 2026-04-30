import os
import sys
import colorsys
import platform
import subprocess

import tkinter as tk
from tkinter import font as tkfont


def safely_import_tkinterdnd2():
    """Check if tkinterdnd2 can be fully initialized.

    Returns the tkinterdnd2 module if safe, else None.

    """

    check_code = """
import sys
try:
    import tkinterdnd2
    root = tkinterdnd2.TkinterDnD.Tk()
    root.withdraw()
    root.destroy()
    sys.exit(0)  # Success
except Exception as e:
    sys.exit(1)  # Failure
"""
    try:
        # Run the check in an isolated process
        result = subprocess.run(
            [sys.executable, "-c", check_code],
            capture_output=True,
            timeout=5 # Prevent hanging on some Intel Mac builds
        )

        if result.returncode == 0:
            import tkinterdnd2
            return tkinterdnd2
    except Exception:
        pass
    return None

def get_hex_colour(rgb, brightness=None):
        h,l,s = colorsys.rgb_to_hls(rgb[0], rgb[1], rgb[2])
        if brightness is not None:
            l = brightness
        r,g,b = [int(x * 255) for x in colorsys.hls_to_rgb(h,l,s)]
        colour = f"#{r:02X}{g:02X}{b:02X}"
        return colour

def is_venv():
    """Return if running in a virtual environment.

    Returns
    -------
    venv : bool
        whether or not running in virtual environment

    Note
    ----
    Only covers virual environments created with `pipx`, `virtualenv`, `venv`,
    and `pyvnenv`.

    """

    real_prefix = getattr(sys, "real_prefix", None)
    base_prefix = getattr(sys, "base_prefix", sys.prefix)

    return (base_prefix or real_prefix) != sys.prefix


def get_config_folder():
    """Return ZAP configuration folder

    If running in a virtual environment, the ZAP configuration folder is
    `/path/to/environment/.zap/`, otherwise it is `$HOME/.zap`.

    Returns
    -------
    configuration_folder : str
        the ZAP configuration folder

    """

    home = os.getenv('USERPROFILE')
    if home is None:
        home = os.getenv('HOME')
    if is_venv():
        home = sys.prefix
    return os.path.join(home, ".zap")


class FontBase:

    def __init__(self, parent, name="TkDefaultFont", family=None, size=None):
        self.root = parent.nametowidget(".")
        self._name = name
        target_font = tkfont.nametofont(self._name)
        if family is None:
            family = target_font.actual("family")
        self._family = family
        if size is None:
            size = target_font.actual("size")
        self._size = size

        tkfont.nametofont(self.name).configure(family=self._family,
                                               size=self._size)

    @property
    def name(self):
        return self._name

    @property
    def family(self):
        return self._family

    @property
    def size(self):
        return self._size

    def _px(self, offset):
        if tk.TclVersion >= 9:
            return -abs(self.size + offset)
        else:
            return self.size + offset

    def spec(self, size_offset=0, weight="normal", slant="roman"):
        return f"{{{self._family}}} {self._px(size_offset)} {weight} {slant}"

    def font(self, size_offset=0, weight="normal", slant="roman"):
        return tkfont.Font(root=self.root, family=self._family,
                           size=self._px(size_offset),
                           weight=weight, slant=slant)


class Theme:
    def __init__(self, scaling):
        if tk.TclVersion >= 9:
            self.scaling = 1
        else:
            self.scaling = scaling

