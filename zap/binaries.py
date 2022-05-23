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


def download_ffmpeg(progress=None):
    platform = get_platform()
    url_base = "https://github.com/zipped-album/zap-binaries/raw/main/ffmpeg"

    if progress:
        progress(0, 100, "")

    try:
        filename = f"ffmpeg5-{platform}.zip"
        url = f"{url_base}/{filename}"
        r = Request(url, headers={"Accept-Encoding": "gzip; deflate"})
        u = urlopen(r)
    except Exception:
        filename = f"ffmpeg4-{platform}.zip"
        url = f"{url_base}/{filename}"
        r = Request(url, headers={"Accept-Encoding": "gzip; deflate"})
        u = urlopen(r)

    with TemporaryFile() as f:
        meta = u.info()
        try:
            file_size = int(u.getheader('Content-Length'))
            file_size_dl = 0
            block_size = 8192
            percents = 0
            while True:
                buffer = u.read(block_size)
                if not buffer:
                    break
                file_size_dl += len(buffer)
                f.write(buffer)
                if progress:
                    percents_new = int(100.0 * file_size_dl / float(file_size))
                    if percents_new > percents:
                        percents = percents_new
                        progress(percents, 100, filename)
        except Exception:
            if progress:
                progress(0, 100, filename)
            chunk = u.read()
            while chunk:
                f.write(chunk)
                chunk = u.read()
        if progress:
            progress(100, 100, filename)

        path = os.path.abspath(os.path.join(os.path.split(__file__)[0], "lib"))
        if not os.path.isdir(path):
                os.makedirs(path)

        f_zip = ZipFile(f)
        check = f_zip.testzip()
        assert check is None
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
