from .assets import has_ffmpeg, download_ffmpeg


def run():
    if not has_ffmpeg():
        while True:
            get = input("No suitable FFmpeg installation found. " + \
                        "Download local copy? [Y/n]: ")
            if get.lower() == "n":
                break
            elif get.lower() in ("y", ""):
                download_ffmpeg()
                break

    from .zap import run as run_zap
    run_zap()

if __name__ == "__main__":
    run()
