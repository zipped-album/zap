# Zipped Album Player (ZAP)

***A simple Python-based cross-platform player for the [Zipped Album](https://github.com/zipped-album/zlbm) format***

<img width="1136" alt="ZAP_MacOS_Screenshot" src="https://user-images.githubusercontent.com/2971539/125360695-8c9cee00-e36c-11eb-86dc-e80de0b0cf35.png">

## Features

* MacOS, Windows and Linux support
* Digital booklet slideshow
* Keyboard navigation (with Vi-like alternatives)
* Fullscreen mode


## Installation

ZAP can be installed with [pipx](https://pypa.github.io/pipx/):
```
pipx install zap
```

### Detailed instructions

#### Linux

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
   pipx install zap
   ```
   
#### MacOS

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
   pipx install zap
   ```

#### Windows

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
   pipx install zap
   ```

## Usage

After successful installation ZAP can be started by calling the command `zap`.

### Keyboard navigation

```
Play/Pause:                               Return           |      Space
Select next track:                        Down             |      j    
Select previous track:                    Up               |      k    
Select first track:                       Home             |      gg   
Seek forward:                             Right            |      l    
Seek backward:                            Left             |      h    
Seek to beginning:                        Numpad 0         |      0    
Show next slide:                          Shift-Right      |      L    
Show previous slide:                      Shift-Left       |      H    
Increase volume:                          Shift-Right      |      K    
Decrease volume:                          Shift-Left       |      J    
```

## FAQ

* **Where can I find music in a format ZAP plays?**

   ZAP plays [Zipped Albums](https://github.com/zipped-album/zlbm), a simple one-file format for digital audio. Basically, these are ZIP archives of FLAC or Opus files with an optional digital booklet and playlist. Albums downloaded from [Bandcamp](https://bandcamp.com) in FLAC format, for instance, are compatible, but you can also easily create them yourself from your existing music.
      
* **Why is there no sound when playing 24 bit files?**

  The OpenAL audio driver does not support 24 bit yet. On MacOS this is the default and only supported driver. On Linux this driver can be used (OpenAL libraries need to be installed though) when no PulseAudio is found on the system. However, keep in mind that [24 bit as distribution format is silly](https://web.archive.org/web/20190103133529/http://people.xiph.org/~xiphmont/demo/neil-young.html).

* **Why is ZAP on Linux using slightly more CPU than on the other OS?**
  When using the PulseAudio driver (default when PulseAudio is found on the system), I need to tick the event loop faster to prevent strange PulseAudio crashes. This is not the case with the OpenAL driver (but see above).

* **Why is fullscreen mode only working on the first display in a multi-display setup?**

  Because Tkinter is not really aware of multiple displays. Currently, I could only make fullscreen mode use the current display on Windows.
  

