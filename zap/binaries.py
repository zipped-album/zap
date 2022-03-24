import os
import sys
import platform
import sysconfig
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from tempfile import TemporaryFile
from zipfile import ZipFile
from shutil import copyfileobj


def _f(q):
    try:
        import os
        import platform
        if platform.system() == "Windows":
            path = "PATH"
            sep = ";"
        else:
            path = "LD_LIBRARY_PATH"
            sep = ":"
        if not os.environ.get(path):
            os.environ[path] = ""
        os.environ[path] += sep + os.path.abspath(
            os.path.join(os.path.split(__file__)[0], "lib"))
        import pyglet
        pyglet.options['search_local_libs'] = True
        q.put(pyglet.media.codecs.have_ffmpeg())
    except Exception:
        q.put(False)

def has_ffmpeg():
    import multiprocessing
    q = multiprocessing.Queue()
    multiprocessing.freeze_support()
    p = multiprocessing.Process(target=_f, args=(q,))
    p.start()
    p.join()
    return q.get()

def get_platform():
    """Return a string with current platform (system and machine architecture).

    This attempts to improve upon `sysconfig.get_platform` by fixing some
    issues when running a Python interpreter with a different architecture than
    that of the system (e.g. 32bit on 64bit system, or a multiarch build),
    which should return the machine architecture of the currently running
    interpreter rather than that of the system (which didn't seem to work
    properly). The reported machine architectures follow platform-specific
    naming conventions (e.g. "x86_64" on Linux, but "x64" on Windows).

    Example output strings for common platforms:

        darwin_(ppc|ppc64|i368|x86_64|arm64)
        linux_(i686|x86_64|armv7l|aarch64)
        windows_(x86|x64|arm32|arm64)

    """

    system = platform.system().lower()
    machine = sysconfig.get_platform().split("-")[-1].lower()
    is_64bit = sys.maxsize > 2 ** 32

    if system == "darwin": # get machine architecture of multiarch binaries
        if any([x in machine for x in ("fat", "intel", "universal")]):
            machine = platform.machine().lower()

    elif system == "linux":  # fix running 32bit interpreter on 64bit system
        if not is_64bit and machine == "x86_64":
            machine = "i686"
        elif not is_64bit and machine == "aarch64":
                machine = "armv7l"

    elif system == "windows": # return more precise machine architecture names
        if machine == "amd64":
            machine = "x64"
        elif machine == "win32":
            if is_64bit:
                machine = platform.machine().lower()
            else:
                machine = "x86"

    # some more fixes based on examples in https://en.wikipedia.org/wiki/Uname
    if not is_64bit and machine in ("x86_64", "amd64"):
        if any([x in system for x in ("cygwin", "mingw", "msys")]):
            machine = "i686"
        else:
            machine = "i386"

    return f"{system}_{machine}"

def show_progress(progress, info="", length=46, symbols="[= ]", decimals=0):
    """Show the progress of a process with a simple text-based progress bar.

    Parameters
    ----------
    progress : (numeric, numeric)
        the current progress to be shown (count, total)
    info : str, optional
        the additional custom info displayed on the right (default="")
    length : int, optional
        the length of the progress bar displayed in the middle (default=40)
    symbols : (chr, chr, chr, chr), optional
        the symbols used to draw the progress bar (default="[= ]")
    decimals : int, optional
        the decimal places of the percantage displayed on the left (default=1)

    """

    percent = progress[0] / progress[1] * 100
    rjust = 3 + (decimals > 0) + decimals
    percentage = f"{percent:{rjust}.{decimals}f}%"
    filled_length = int(round(length * progress[0] / float(progress[1])))
    bar = f"{symbols[0]}{symbols[1] * filled_length}" \
          f"{symbols[2] * (length - filled_length)}{symbols[3]}"
    print(f"\033[K\r{percentage} {bar}{' ' + info if info else ''}", end="")
    if progress[0] == progress[1]:
        print("")

def download_ffmpeg():
    platform = get_platform()
    url_base = "https://github.com/zipped-album/zap-binaries/raw/main/ffmpeg"
    filename = f"ffmpeg4-{platform}.zip"
    url = f"{url_base}/{filename}"

    try:
        r = Request(url, headers={"Accept-Encoding": "gzip; deflate"})
        u = urlopen(r)
    except HTTPError as e:
        if e.status == 404:
            print(f"No download available for this platform ({platform}).")
        else:
            print(f"Download of {url} failed ({e.status} {e.msg}).")
        return

    with TemporaryFile() as f:
        meta = u.info()
        try:
            file_size = int(u.getheader('Content-Length'))
            file_size_dl = 0
            block_sz = 8192
            while True:
                buffer = u.read(block_sz)
                if not buffer:
                    break
                file_size_dl += len(buffer)
                f.write(buffer)
                show_progress((file_size_dl, file_size),
                              info=f"{filename}")
        except Exception:
            show_progress((0, 100), info=f"{filename}")
            chunk = u.read()
            while chunk:
                f.write(chunk)
                chunk = u.read()
            show_progress((100, 100), info=f"{filename}")

        path = os.path.abspath(os.path.join(os.path.split(__file__)[0], "lib"))
        if not os.path.isdir(path):
                os.makedirs(path)

        print("\033[K\rExtracting...", end="")
        f_zip = ZipFile(f)
        check = f_zip.testzip()
        if check is not None:
            print("\033[K\rExtracting...Download was corrupted!")
            return
        root = f_zip.namelist()[0]
        files = [x for x in f_zip.namelist() if not x.startswith("_")]
        files_installed = 0
        for member in files:
            filename = os.path.basename(member)
            source = f_zip.open(member)
            target = open(os.path.join(path, member), 'wb')
            with source, target:
                copyfileobj(source, target)
            files_installed += 1
        print("\033[K\rExtracting...Done!")
