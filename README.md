# Zipped Album Player (ZAP)

***A simple Python-based cross-platform player for the [Zipped Album](https://github.com/zipped-album/zlbm) format***

<img width="1136" alt="zap_macos_preset4default" src="https://user-images.githubusercontent.com/2971539/147706659-6b42018e-a304-419c-b030-c3232e691165.png">

## Features

* MacOS, Windows and Linux support
* Digital booklet slideshow
* Keyboard navigation (with Vi-like alternatives)
* Fullscreen mode

## Installation

ZAP can be installed with [pipx](https://pypa.github.io/pipx/):
```
pipx install Zipped-Album-Player
```

**Note:**

ZAP relies on FFmpeg to decode audio. If FFmpeg cannot be found on the system,
ZAP will attempt to download a local copy the first time it is started.

### Windows

1. **Make sure you have Python 3 with Tkinter support installed**
   
   If not, install it. For instance with this installer: https://www.python.org/ftp/python/3.10.4/python-3.10.4-amd64.exe
   
2. **Install pipx**
   
   ```
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   ```
   
3. **Install ZAP**

   ```
   pipx install Zipped-Album-Player
   ```

### MacOS

1. **Make sure you have Python 3 with Tkinter support installed**
   
   If not, install it. For instance with this installer: https://www.python.org/ftp/python/3.10.4/python-3.10.4-macos11.pkg
   
2. **Install pipx**
   
   ```
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   ```
   
3. **Install ZAP**

   ```
   pipx install Zipped-Album-Player
   ```

**Note**:

On ARM-based Macs you will, for now, still need to have FFmpeg 4 (shared
libraries) installed on the system. You can install them, for instance, using
Homebrew:
```
brew install ffmpeg@4
```
   
### Linux

1. **Make sure you have Python 3 with Tkinter support installed**

   If not, install it. For instance, on Debian-based distros:
   ```
   sudo apt install python3 python3-venv python3-pip python3-tk
   ```
   
2. **Make sure OpenAL is installed**

   If not, install it. For instance, on Debian-based distros:
   ```
   sudo apt install libopenal1
   ```
   
3. **Make sure PyMuPDF and ImageTk are installed**

   If not, install them. For instance, on Debian-based distros:
   ```
   sudo apt install python3-fitz python3-pil.imagetk
   ```

5. **Install pipx**
   
   ```
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   ```
      
6. **Install ZAP**

   ```
   pipx install --system-site-packages Zipped-Album-Player
   ```
   
## Usage

After successful installation, ZAP can be started with either
```
zap [--exact] [ZIPPED_ALBUM]
````
or 
```
zipped-album-player [--exact] [ZIPPED_ALBUM]
```
where `ZIPPED_ALBUM` is an optional path to a Zipped Album file.
If `--exact` is given, ZAP will show all booklets and images in alphabetic
order, will not attempt to try alternative encodings of of wrongly encoded
filenames in the ZIP file to match filenames in a playlist, and will not apply
any fixes to track numbering.
If `ZIPPED_ALBUM` is a directory, ZAP will set the initial directory
of the "Open..." dialogue to that.

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
      
* **Couldn't you provide simple one-click installers/executables for ZAP?**

  Yes, I could use something like PyInstaller, and I might do that at some point. For now, however, I think pipx is a good enough solution.

* **Why do I not hear any sound when playing an album in ZAP?**

  ZAP might have selected the "Silent" audio driver. ZAP relies on either DirectSound (Windows) or OpenAL (MacOS, Linux, Windows) to play back audio. On Windows, DirectSound should be installed by default. On MacOS, OpenAL should be installed by default. On Linux, OpenAL might not be installed by default. Install it with your package manager (for instance on Debian-based distros with `apt install libopenal1`). 
  
* **Why is the bit depth of my tracks reported as "24→16 bit"?**

  When ZAP uses OpenAL, it will resample to 16 bit during playback for tracks with bit depths higher than that, since OpenAL does not support those yet. This process will involve dithering (with moderate noise shaping) to prevent quantization noise. However, since [distribution/listening formats do not benefit from bit depths higher than 16](https://web.archive.org/web/20190103133529/http://people.xiph.org/~xiphmont/demo/neil-young.html), I suggest to obtain properly mastered 16 bit sources when available.
  
* **Why is the channel count on my 5.1 surround track reported as "6ch→stereo"?**

  There is currently no mutli-channel support and everything with more than 2 channels is down-mixed to stereo.

* **Why is fullscreen mode only working on the first display in a multi-display setup?**

  Because Tkinter is not really aware of multiple displays, unfortunately.
