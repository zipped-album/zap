# Zipped Album Player (ZAP)

***A simple Python-based cross-platform player for the [Zipped Album](https://github.com/zipped-album/zlbm) format***

<img width="1136" alt="ZAP_Screenshot_MacOS" src="https://user-images.githubusercontent.com/2971539/126552558-b43b759c-c274-4659-aa04-b773fcf07487.png">

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

### Detailed instructions

#### MacOS

1. **Make sure you have Python 3 with Tkinter support installed**
   
   If not, install it. For instance: https://www.python.org/ftp/python/3.9.7/python-3.9.7-macosx10.9.pkg.
   
2. **Make sure FFmpeg shared libraries are installed**
   
   If not, install them.
   For instance, using Homebrew:
   ```
   brew install ffmpeg
   ```
   
3. **Install pipx**
   
   ```
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   ```
   
4. **Install ZAP**

   ```
   pipx install Zipped-Album-Player
   ```

#### Windows

1. **Make sure you have Python 3 with Tkinter support installed**
   
   If not, install it. For instance: https://www.python.org/ftp/python/3.9.7/python-3.9.7-amd64.exe
   
2. **Make sure FFmpeg shared libraries are installed**
   
   If not, install them.
   For example:
    * Download https://github.com/GyanD/codexffmpeg/releases/download/4.4/ffmpeg-4.4-full_build-shared.zip
    * Unzip to `C:\FFmpeg\`
    * Add `C:\FFmpeg\bin\` to your environment variable `PATH`
   
3. **Install pipx**
   
   ```
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   ```
   
4. **Install ZAP**

   ```
   pipx install Zipped-Album-Player
   ```

#### Linux

1. **Make sure you have Python 3 with Tkinter support installed**

   If not, install it. For instance, on Debian-based distros:
   ```
   sudo apt install python3 python3-venv python3-pip python3-tk
   ```
   
2. **Make sure FFmpeg shared libraries are installed**
   
   If not, install them. For instance, on Debian-based distros:
   ```
   sudo apt install ffmpeg
   ```
   
3. **Make sure OpenAL is installed**

   If not, install it. For instance, on Debian-based distros:
   ```
   sudo apt install libopenal1
   ```
   
4. **Install pipx**
   
   ```
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   ```
   
5. **Install ZAP**

   ```
   pipx install Zipped-Album-Player
   ```
   
## Usage

After successful installation, ZAP can be started with either
```
zap [ZIPPED_ALBUM]
````
or 
```
zipped-album-player [ZIPPED_ALBUM]
```
where `ZIPPED_ALBUM` is an optional path to a Zipped Album file.

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
