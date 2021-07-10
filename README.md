# ZAP
**Zipped Album Player** - A simple cross-platform player for the [Zipped Album](https://github.com/zipped-album/zlbm) format

 <img width="1136" alt="ZAP_MacOS_Screenshot" src="https://user-images.githubusercontent.com/2971539/125173823-86b6d980-e1c1-11eb-87c4-cdd2c33956a0.png">

## Installation

### Linux

1. **Make sure you have Python 3 with Tkinter support installed**

   If not, use your package manager to install it.
   For instance, on Debian-based distros:
   ```
   apt install python3 python3-tk
   ```
   
3. **Make sure FFmpeg shared libraries are installed**
   
   If not, use your package manager to install them.
   For instance, on Debian-based distros:
   ```
   apt install python3-tk ffmpeg
   ```
   
2. **Install pipx**
   
   ```
   pip3 install pipx
   ```
   
3. **Install ZAP**

   ```
   pipx install git+https://github.com/zipped-album/zap.git
   ```

4. **Run ZAP**
   
   ```
   zap
   ```
   
### MacOS

1. **Make sure you have Python 3 with Tkinter support installed***
   
   If not, download and run https://www.python.org/ftp/python/3.9.6/python-3.9.6-macosx10.9.pkg
   
2. **Make sure FFmpeg shared libraries are installed**
   
   If not, install them.
   For instance, using Homebrew:
   ```
   brew install ffmpeg
   ```
   
3. **Install pipx**
   
   ```
   pip3 install pipx
   ```
   
4. **Install ZAP**

   ```
   pipx install git+https://github.com/zipped-album/zap.git
   ```

5. **Run ZAP**
   
   ```
   zap
   ```

### Windows

1. **Make sure you have Python 3 with Tkinter support installed***
   
   If not, download and run https://www.python.org/ftp/python/3.9.6/python-3.9.6-amd64.exe
   
2. **Make sure FFmpeg shared libraries are installed**
   
   If not, install them.
   For example:
    * Download https://github.com/GyanD/codexffmpeg/releases/download/4.4/ffmpeg-4.4-full_build-shared.zip
    * Unzip to `C:\FFmpeg\`
    * Add `C:\FFmpeg\bin\` to your environment variable `PATH`
   
3. **Install pipx**
   
   ```
   pip3 install pipx
   ```
   
4. **Install ZAP**

   ```
   pipx install git+https://github.com/zipped-album/zap.git
   ```

5. **Run ZAP**
   
   ```
   zap
   ```

## FAQ

* **Why is there no sound when playing 24 bit files?**

  The OpenAL audio driver does not support 24 bit yet. On MacOS this is the default and only supported driver. On Linus this driver can be used (OpenAL libraries need to be installed though) when no PulseAudio is found on the system. Also, [24 bit as distribution format is silly](https://web.archive.org/web/20190103133529/http://people.xiph.org/~xiphmont/demo/neil-young.html).

* **Why is ZAP on Linux using slightly more CPU than on the other OS?**
  When using the PulseAudio driver (default when PulseAudio is found on the system), I need to tick the event loop faster to prevent strange PulseAudio crashes. This is not the case with the OpenAL driver (but see above).

* **Why is fullscreen mode only working on the first display in a multi-display setup?**

  Because Tkinter is not really aware of multiple displays. Currently, I could only make fullscreen mode use the current display on Windows.
  

