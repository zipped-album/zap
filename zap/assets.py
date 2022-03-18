import os
import sys
import platform
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
            PATH = "PATH"
        else:
            PATH = "LD_LIBRARY_PATH"
        if not os.environ.get(PATH):
            os.environ[PATH] = ""
        os.environ[PATH] += ":" + os.path.abspath(
            os.path.join(os.path.split(__file__)[0], "lib"))
        import pyglet
        q.put(pyglet.media.codecs.have_ffmpeg())
    except Error:
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
    if sys.platform == 'win32':
        if sys.maxsize > 2 ** 32:
            return "windows_x64"
        else:
            return "windows_x86"
    elif sys.platform.startswith("linux"):
        if "armv7l" in sys.platform or "armv7l" in os.uname():
            return "linux_armv7l"
        elif "aarch64" in sys.platform or "aarch64" in os.uname():
            return "linux_aarch64"
        elif sys.maxsize > 2 ** 32:
            return "linux_x64"
        else:
            return "linux_x86"
    elif sys.platform == "darwin":
        if "ARM64" in sys.platform or "ARM64" in os.uname():
            return "macos_arm64"
        elif sys.maxsize > 2 ** 32:
            return "macos_x64"

def show_progress(progress, info="", length=45, symbols="[= ]", decimals=1):
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
    url_base = \
        "https://github.com/zipped-album/zap/raw/main/assets/ffmpeg"
    filename = f"ffmpeg-{platform}.zip"
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
