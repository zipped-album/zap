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
pipx install zipped-album-player
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
   pipx install zipped-album-player
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
   pipx install zipped-album-player
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
   pipx install zipped-album-player
   ```

## Usage

After successful installation ZAP can be started by calling the command `zap` (or `zipped-album-player`).

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
      
* **Why do I not hear any sound when playing an album in ZAP?**

  If you are on Linux, you need to have either OpenAL (reccomended) or PulseAudio installed. PulseAudio comes as default in most distos these days. OpenAL can be installed with your package manager (for instance on Debian-based distros with `apt install libopenal1`).
  
* **Why do I hear glitches/skips/crackling when playing an album in ZAP?**

  If you are on Linux, this might be an issue with PulseAudio. You could either install OpenAL (recommended; see previous answer) or try to fix the PulseAudio problems (see e.g. https://wiki.archlinux.org/title/PulseAudio/Troubleshooting#Glitches,_skips_or_crackling.
  
* **Why is the bit depth of my tracks reported as "24→16 bits"?**

  OpenAL does not support bit depths higher than 16, and ZAP will resample to 16 if tracks have higher bit depths. This process, however, might lead to quantization noise. Please also note that [distribution/listening formats do not benefit from bit depths higher than 16](https://web.archive.org/web/20190103133529/http://people.xiph.org/~xiphmont/demo/neil-young.html). I hence suggest to try to obtain properly dithered 16 bit versions whenever possible.

* **Why is fullscreen mode only working on the first display in a multi-display setup?**

  Because Tkinter is not really aware of multiple displays. Currently, I could only make fullscreen mode use the current display on Windows.
  

