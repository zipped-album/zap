import os
import sys
import shutil
import colorsys
import platform
import tempfile
import textwrap
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

def delete_folder_on_exit(path, wait_pid=None, max_tries=5, sleep=0.5):
    """Delete a folder after the application has exited.

    This launches a detached Python helper script that waits until the PID
    does not exist anymore, then deletes the folder and removes the helper
    script.

    Parameters
    ----------
    path : str
        the path of the folder to delete
    wait_pid : int, optional
        the PID of the process to wait for before attempting deletion; uses
	the PID of current process if None(default=None)
    max_tries : int, optional
        the amount of times a deletion should be attempted (default=5)
    sleep: float, optional
        the time to sleep in between attempts (default=0.5)

    """

    if wait_pid is None:
        wait_pid = os.getpid()
    python = sys.executable
    helper_code = textwrap.dedent(f"""\
        import os, time, shutil, sys, traceback
        pid = {wait_pid}
        target = {path!r}
        helper = {{}}
        try:
            # wait for PID to exit
            while True:
                try:
                    os.kill(pid, 0)
                except Exception:
                    break
                time.sleep({sleep})
            # attempt removal a few times
            for _ in range({max_tries}):
                try:
                    if os.path.exists(target):
                        shutil.rmtree(target)
                    break
                except Exception:
                    time.sleep({sleep})
            # remove helper file itself
            try:
                os.remove(__file__)
            except Exception:
                pass
        except Exception:
            traceback.print_exc()
        finally:
            sys.exit(0)
    """)
    fd, helper_path = tempfile.mkstemp(prefix="delete_helper_", suffix=".py")
    os.close(fd)
    with open(helper_path, "w", encoding="utf-8") as f:
        f.write(helper_code)
    # Launch detached helper
    if platform.system() == "Windows":
        # CREATE_NO_WINDOW | DETACHED_PROCESS
        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen([python, helper_path],
                         creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                         close_fds=True)
    else:
        subprocess.Popen([python, helper_path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True)


class FontBase:

    def __init__(self, parent, family, size):
        self.root = parent.nametowidget(".")
        self._family = family
        self._size = size

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


