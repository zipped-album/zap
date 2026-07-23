import os
import sys
import math
import platform
import tempfile

from .utils import get_config_folder

if platform.system() == "Windows":
    path = "PATH"
    sep = ";"
else:
    path = "LD_LIBRARY_PATH"
    sep = ":"
if not os.environ.get(path):
    os.environ[path] = os.path.abspath(
        os.path.join(get_config_folder(), "ffmpeg"))
else:
    os.environ[path] += sep + os.path.abspath(
        os.path.join(get_config_folder(), "ffmpeg"))

import pyglet
pyglet.options['audio'] = ('silent')

assert pyglet.media.codecs.have_ffmpeg()

from pyglet.media.codecs.ffmpeg import *


def _discover_available_audio_systems():
    available_audio_systems = {}

    import importlib

    drivers = {"XAudio2": "xaudio2", "DirectSound": "directsound",
               "PulseAudio": "pulse", "OpenAL": "openal"}

    for driver in drivers:
        try:
            # Dynamically import the driver's interface module
            module = importlib.import_module(
                f"pyglet.media.drivers.{drivers[driver]}")
            interface = importlib.import_module(
                f"pyglet.media.drivers.{drivers[driver]}.interface")
            drv = module.create_audio_driver()
            d = {"driver": drivers[driver],
                 "int32": pyglet.media.AUDIO_SAMPLE_FORMAT_S32
                 in drv.sample_formats,
                 "float32": pyglet.media.AUDIO_SAMPLE_FORMAT_F32
                 in drv.sample_formats}

            drv.delete()
            available_audio_systems[driver] = d

        except:
            pass

    # Add Silent output
    available_audio_systems["Silent"] = {"driver": "silent",
                                         "int32": True,
                                         "float32": False}

    return available_audio_systems

AVAILABLE_AUDIO_SYSTEMS = _discover_available_audio_systems()


class AudioPlayer:
    """A class implementing an audio player.

    This is a wrapper around pyglet.media.Player.

    """

    available_audio_systems = AVAILABLE_AUDIO_SYSTEMS
    available_sample_formats = {}
    for system in AVAILABLE_AUDIO_SYSTEMS:
        d = {"Automatic": None, "16-bit": pyglet.media.AUDIO_SAMPLE_FORMAT_S16}
        if AVAILABLE_AUDIO_SYSTEMS[system]["float32"]:
            d["32-bit float"] = pyglet.media.AUDIO_SAMPLE_FORMAT_F32
        available_sample_formats[system] = d
    available_sample_rates = {
        "Automatic": None,
        "44100 Hz": pyglet.media.AUDIO_SAMPLE_RATE_44100,
        "48000 Hz": pyglet.media.AUDIO_SAMPLE_RATE_48000,
        "88200 Hz": pyglet.media.AUDIO_SAMPLE_RATE_88200,
        "96000 Hz": pyglet.media.AUDIO_SAMPLE_RATE_96000
    }
    available_channel_modes = {
        "Automatic": None,
        "Mono": pyglet.media.AUDIO_CHANNELS_MONO,
        "Dual-Mono": pyglet.media.AUDIO_CHANNELS_DUAL_MONO,
        "Stereo": pyglet.media.AUDIO_CHANNELS_STEREO
    }

    def __init__(self, audio_system, sample_format, sample_rate, channel_mode,
                 hq_resampling):
        """Create an AudioPlayer object.

        Parameters
        ----------
        audio_system : str
            the pyglet audio driver to use ('XAudio2', 'DirectSound', 'OpenAL',
            'PulseAudio')
        sample_format : str
            the FFmpeg output format to use ("Automatic", "16-bit",
            "32-bit float")
        sample_rate : str
            the FFmpeg sample rate to use ("Automatic", "44100 Hz", "48000 Hz",
            "88200 Hz", "96000 Hz")
        channel_mode : str
            the FFmpeg output channel mode to use ("Automatic", "Mono",
            "Dual-Mono", Stereo")
        hq_resampling : bool
            whether to use hiqh-quality resampling

        """

        audio_driver = self.available_audio_systems[audio_system]["driver"]
        module = __import__(f"pyglet.media.drivers.{audio_driver}",
                            fromlist=['create_audio_driver'])
        pyglet.media.drivers._audio_driver = module.create_audio_driver()

        self._audio_system = audio_system
        self._sample_format = sample_format
        self._sample_rate = sample_rate
        self._channel_mode = channel_mode
        self._hq_resampling = hq_resampling
        if pyglet.version.startswith("3"):
            self._player = pyglet.media.AudioPlayer()
        else:
            self._player = pyglet.media.Player()
        self._on_eos = None
        self._clear_on_queue = True
        self.offset = 0

        audio_settings = []
        if sample_format != "Automatic":
            audio_settings.append(sample_format)
        if sample_rate != "Automatic":
            audio_settings.append(sample_rate)
            if hq_resampling:
                audio_settings.append("(HQ)")
        if channel_mode != "Automatic":
            audio_settings.append(channel_mode)
        print(f"Audio System: {audio_system} {' '.join(audio_settings)}")

    def __del__(self):
        """Delete an AudioPlayer object."""

        self._player.delete()

    @property
    def audio_system(self):
        return self._audio_system

    @property
    def sample_format(self):
        return self._sample_format

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def channel_mode(self):
        return self._channel_mode

    @property
    def hq_resampling(self):
        return self._hq_resampling

    @property
    def is_playing(self):
        return self._player.playing

    @property
    def buffer_size(self):
        if self.is_playing:
            return self._player._audio_player._buffered_data_ideal_size
    @property
    def buffer_time(self):
        if self.is_playing:
            rate = self._player._audio_player.source.audio_format.sample_rate
            size = self._player._audio_player.source.audio_format.sample_size
            channels = self._player._audio_player.source.audio_format.channels
            return self.buffer_size / rate / (size / 8 * channels)

    @property
    def time(self):
        return self._player.time - self.offset

    @property
    def volume(self):
        return self._player.volume

    @volume.setter
    def volume(self, value):
        if type(value) is float and 0.0 <= value <= 1.0:
            self._player.volume = value

    @property
    def eos_callback(self):
        return self._on_eos

    @eos_callback.setter
    def eos_callback(self, value):
        if callable(value):
            self._on_eos = value

    @property
    def clear_on_queue(self):
        return self._clear_on_queue

    @clear_on_queue.setter
    def clear_on_queue(self, value):
        if type(value) == bool:
            self._clear_on_queue = value

    def play(self):
        """Start playback."""

        self._player.play()

    def pause(self):
        """Pause playback."""

        self._player.pause()

    def clear(self):
        """Clear the queue."""

        self._player.delete()
        self._player._source = None
        self._player._playlists.clear()
        self._player._timer.reset()

    def queue(self, tracks):
        """Fill the play queue.

        Parameters
        ----------
        tracks : list of zipfile.ZipExtFile objects
            the tracks to fill the queue

        """

        if not type(tracks) in (list, tuple):
            tracks = [tracks]
        if self.clear_on_queue:
            self.clear()
            self.clear_on_queue = False
        for track in tracks:
            if pyglet.version.startswith("3"):
                _load = pyglet.media._load
            else:
                _load = pyglet.media.load
            source = _load(
                track.name, file=track, decoder=FFmpegDecoder(),
                audio_sample_format=self.available_sample_formats[
                    self.audio_system][self.sample_format],
                audio_sample_rate=self.available_sample_rates[self.sample_rate],
                audio_channels=self.available_channel_modes[self.channel_mode],
                audio_resample_hq=self.hq_resampling)

            self._player.queue(source)

    def seek(self, time):
        """Seek to a certain point in time.

        time : float
            the point in time to seek to (in seconds)

        """

        playing = self.is_playing
        if playing:
            self._player.pause()
            self.update()
        self._player.seek(time)
        self.update()
        if pyglet.__version__ <= "2.0.10":
            self._player.seek(time)
            self.update()
        if playing:
            self._player.play()
            self.update()

    def update(self):
        """Update the audio player."""

        if self._player.source is not None:
            if self.time >= self._player.source.duration:
                if self._on_eos is not None:
                    self._on_eos()


class SourceGroup(pyglet.media.SourceGroup):
    """Enhanced SourceGroup with some additions."""

    def __init__(self):
        super().__init__()
        self._advanced = False
        self._advance_callback = None

    @property
    def advance_callback(self):
        return self._advance_callback

    @advance_callback.setter
    def advance_callback(self, value):
        if callable(value):
            self._advance_callback = value

    def _advance(self):
        super()._advance()
        self._advanced = True


class GaplessAudioPlayer(AudioPlayer):
    """A class implementing a gapless audio player.

    This is a wrapper around pyglet.media.Player and pyglet.media.SourceGroup.

    """

    def __init__(self, audio_system, sample_format, sample_rate, channel_mode,
                 hq_resampling):
        """Create an AudioPlayer object.

        Parameters
        ----------
        audio_system : str
            the pyglet audio driver to use ('XAudio2', 'DirectSound', 'OpenAL',
            'PulseAudio')
        sample_format : str
            the FFmpeg output format to use ("Automatic", "16 bit",
            "32 bit float")
        sample_rate : str
            the FFmpeg sample rate to use ("Automatic", "44100 Hz", "48000 Hz",
            "88200 Hz", "96000 Hz")
        channel_mode : str
            the FFmpeg channel mode to ise ("Automatic", "Mono", "Dual-Mone",
            "Stereo")
        hq_resampling : bool
            whether to use high-quality resampling

        """

        super().__init__(audio_system, sample_format, sample_rate,
                         channel_mode, hq_resampling)
        self._on_gapless_eos = None
        self.clear()

    @property
    def eos_gapless_callback(self):
        return self._on_gapless_eos

    @eos_gapless_callback.setter
    def eos_gapless_callback(self, value):
        if callable(value):
            self._on_gapless_eos = value

    @property
    def queue_is_empty(self):
        return self._sourcegroup._sources == []

    def clear(self):
        """Clear the queue."""

        super().clear()
        self._sourcegroup = SourceGroup()
        self._player.queue(self._sourcegroup)
        self._current_duration = None

    def queue(self, tracks):
        """Fill the play queue.

        Parameters
        ----------
        tracks : list of zipfile.ZipExtFile objects
            tracks to fill the queue with

        """

        if not type(tracks) in (list, tuple):
            tracks = [tracks]
        if self.clear_on_queue:
            self.clear()
            self.clear_on_queue = False
        was_empty = len(self._sourcegroup._sources) == 0
        for track in tracks:
            if pyglet.version.startswith("3"):
                _load = pyglet.media._load
            else:
                _load = pyglet.media.load
            self._sourcegroup.add(_load(
                track.name, file=track, decoder=FFmpegDecoder(),
                audio_sample_format=self.available_sample_formats[
                    self.audio_system][self.sample_format],
                audio_sample_rate=self.available_sample_rates[self.sample_rate],
                audio_channels=self.available_channel_modes[self.channel_mode],
                audio_resample_hq=self.hq_resampling))
        if was_empty:
            self._current_duration = self._sourcegroup._sources[0].duration

    def seek(self, time):
        """Seek to a certain point in time.

        Parameters
        ----------
        time : float
            the point in time to seek to (in seconds)

        """

        if self._sourcegroup._advanced:
            return
        if self._current_duration is not None:
            if time > self._current_duration - 0.2:
                time = self._current_duration - 0.2
            if self.time < self._current_duration - 0.2:
                super().seek(time)
                self.offset = 0

    def update(self):
        """Update the audio player."""

        if self._sourcegroup._sources != []:
            if self._current_duration is not None:
                if self._sourcegroup._advanced:
                    self._sourcegroup._advanced = False
                    self._on_gapless_eos()
                if self.time > self._current_duration:
                    if len(self._sourcegroup._sources) > 0:
                        self.offset += self._current_duration
                        #self._player._timer.set_time(self.time - \
                                                     #self._current_duration)
                        self._current_duration = \
                            self._sourcegroup._sources[0].duration
                    else:
                        self._current_duration = None
        else:
            self._on_eos()
