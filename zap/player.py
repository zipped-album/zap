import os
import sys
import platform
import tempfile

if platform.system() == "Windows":
    path = "PATH"
    sep = ";"
else:
    path = "LD_LIBRARY_PATH"
    sep = ":"
if not os.environ.get(path):
    os.environ[path] = os.path.abspath(
        os.path.join(os.path.split(__file__)[0], "lib"))
else:
    os.environ[path] += sep + os.path.abspath(
        os.path.join(os.path.split(__file__)[0], "lib"))

import pyglet
pyglet.options['search_local_libs'] = True
pyglet.options['audio'] = ('silent')

try:
    assert pyglet.media.codecs.have_ffmpeg()
except:
    raise RuntimeError("Error loading FFmpeg shared libraries!")

from pyglet.media.codecs.ffmpeg import *

from .__init__ import __author__, __version__



def _discover_available_audio_outputs():
    available_audio_outputs = {}

    try:  # OpenAL
        from pyglet.media.drivers import openal
        driver = openal.create_audio_driver()

        # Monkey patch support for 32-bit float
        float32 = bool(
            openal.lib_openal.alIsExtensionPresent(b"AL_EXT_float32"))
        if float32:
            openal.interface.OpenALBuffer._format_map[(2, 32)] = 65553
        d = {"driver": "openal",
             "int32": False,
             "float32": float32}
        available_audio_outputs["OpenAL"] = d

    except:
        pass

    try:  # PulseAudio
        from pyglet.media.drivers import pulse
        driver = pulse.create_audio_driver()
        d = {"driver": "pulse",
             "int32": False,
             "float32": False}

        # Monkey patch support for 32-bit float
        try:
            def create_sample_spec(self, audio_format):
                """
                Create a PulseAudio sample spec from pyglet audio format.
                """

                from pyglet.media.drivers.pulse import lib_pulseaudio as pa

                _FORMATS = {
                    ('little', 8, 'int'):    pa.PA_SAMPLE_U8,
                    ('big', 8, 'int'):       pa.PA_SAMPLE_U8,
                    ('little', 16, 'int'):   pa.PA_SAMPLE_S16LE,
                    ('big', 16, 'int'):      pa.PA_SAMPLE_S16BE,
                    ('little', 24, 'int'):   pa.PA_SAMPLE_S24LE,
                    ('big', 24, 'int'):      pa.PA_SAMPLE_S24BE,
                    ('little', 32, 'int'):   pa.PA_SAMPLE_S32LE,
                    ('big', 32, 'int'):      pa.PA_SAMPLE_S32BE,
                    ('little', 32, 'float'): pa.PA_SAMPLE_FLOAT32LE,
                    ('big', 32, 'float'):    pa.PA_SAMPLE_FLOAT32BE,
                }
                fmt = (sys.byteorder, audio_format.sample_size,
                       audio_format.sample_type)
                if fmt not in _FORMATS:
                    raise MediaException(
                        f'Unsupported sample size/format: {fmt}')

                sample_spec = pa.pa_sample_spec()
                sample_spec.format = _FORMATS[fmt]
                sample_spec.rate = audio_format.sample_rate
                sample_spec.channels = audio_format.channels
                return sample_spec

            pulse.interface.PulseAudioStream.create_sample_spec = \
                create_sample_spec

            d["int32"] =  True
            d["float32"] = True

        except:
            pass

        available_audio_outputs["PulseAudio"] = d

    except:
        pass

    try:  # DirectSound
        from pyglet.media.drivers import directsound
        driver = directsound.create_audio_driver()
        d = {"driver": "directsound",
             "int32": False,
             "float32": False}

        # Monkey patch support for 24-bit and 32-bit float
        try:
            def _create_wave_format(audio_format):
                from pyglet.media.drivers.directsound import lib_dsound as lib

                if audio_format.channels > 2 or \
                        audio_format.sample_size not in (8, 16, 24, 32):
                    raise MediaException(
                        f'Unsupported audio format: {audio_format}')

                wfx = lib.WAVEFORMATEX()
                if audio_format.sample_type == "float":
                    wfx.wFormatTag = 3
                else:
                    wfx.wFormatTag = lib.WAVE_FORMAT_PCM
                wfx.nChannels = audio_format.channels
                wfx.nSamplesPerSec = audio_format.sample_rate
                wfx.wBitsPerSample = audio_format.sample_size
                wfx.nBlockAlign = wfx.wBitsPerSample * wfx.nChannels // 8
                wfx.nAvgBytesPerSec = wfx.nSamplesPerSec * wfx.nBlockAlign
                return wfx

            directsound.interface._create_wave_format = _create_wave_format

            d["int32"] =  True
            d["float32"] = True

        except:
              pass

        available_audio_outputs["DirectSound"] = d

    except:
        pass

    try:  #XAudio2
        from pyglet.media.drivers import xaudio2
        driver = xaudio2.create_audio_driver()
        d = {"driver": "xaudio2",
             "int32": False,
             "float32": False}

        # Monkey patch to support 24-bit and 32-bit float
        try:
            def _create_xa2_waveformat(audio_format):
                from pyglet.media.drivers.xaudio2 import lib_xaudio2 as lib

                if audio_format.channels > 2 or \
                        audio_format.sample_size not in (8, 16, 24, 32):
                    raise MediaException(
                        f'Unsupported audio format: {audio_format}')

                wfx = lib.WAVEFORMATEX()
                if audio_format.sample_type == "float":
                    wfx.wFormatTag = 3
                else:
                    wfx.wFormatTag = lib.WAVE_FORMAT_PCM
                wfx.nChannels = audio_format.channels
                wfx.nSamplesPerSec = audio_format.sample_rate
                wfx.wBitsPerSample = audio_format.sample_size
                wfx.nBlockAlign = wfx.wBitsPerSample * wfx.nChannels // 8
                wfx.nAvgBytesPerSec = wfx.nSamplesPerSec * wfx.nBlockAlign
                return wfx

            xaudio2.interface._create_xa2_waveformat = _create_xa2_waveformat

            d["int32"] =  True
            d["float32"] = True

        except:
            pass

        available_audio_outputs["XAudio2"] = d

    except:
        pass

    available_audio_outputs["Silent"] = {"driver": "silent",
                                         "int32": True,
                                         "float32": True}

    return available_audio_outputs

AVAILABLE_AUDIO_OUTPUTS = _discover_available_audio_outputs()

def _discover_available_output_formats():
    available_output_formats = {}
    for output in AVAILABLE_AUDIO_OUTPUTS:
        d = {"Automatic": 0, "16-bit": AV_SAMPLE_FMT_S16}
        if AVAILABLE_AUDIO_OUTPUTS[output]["float32"]:
            d["32-bit float"] = AV_SAMPLE_FMT_FLT
        available_output_formats[output] = d
    return available_output_formats

AVAILABLE_OUTPUT_FORMATS = _discover_available_output_formats()


class FFmpegSource(FFmpegSource):
    """Modified FFmpegSource with some fixes.

    Fixes:
        - Close tempfile after writing it
        - Delete tempfile when object is deleted
        - Allow bit depth to be higher than 16
        - Allow fixing target format
        - Dither (and noise shape) on bit reduction

    Original code from the Pyglet project (pyglet.org) is under the following
    license:

    Copyright (c) 2006-2008 Alex Holkner
    Copyright (c) 2008-2021 pyglet contributors
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

      * Redistributions of source code must retain the above copyright
        notice, this list of conditions and the following disclaimer.
      * Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in
        the documentation and/or other materials provided with the
        distribution.
      * Neither the name of pyglet nor the names of its
        contributors may be used to endorse or promote products
        derived from this software without specific prior written
        permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
    "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
    LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
    FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
    COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
    INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
    BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
    LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
    CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
    LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
    ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.

    """


    fixed_tgt_format = 0  # 0, None or False for automatic

    _AV_BITS = {AV_SAMPLE_FMT_U8: 8, AV_SAMPLE_FMT_U8P: 8,
                AV_SAMPLE_FMT_S16: 16, AV_SAMPLE_FMT_S16P: 16,
                AV_SAMPLE_FMT_S32: 32, AV_SAMPLE_FMT_S32P: 32,
                AV_SAMPLE_FMT_FLT: 32, AV_SAMPLE_FMT_FLTP: 32}

    def __init__(self, filename, file=None):
        self._tempfile = None
        if file:
            file.seek(0)
            if platform.system() == "Windows":
                self._tempfile = tempfile.NamedTemporaryFile(delete=False)
            else:
                self._tempfile = tempfile.NamedTemporaryFile(buffering=False)
            self._tempfile.write(file.read())
            filename = self._tempfile.name
            if platform.system() == "Windows":
                self._tempfile.close()

        self._packet = None
        self._video_stream = None
        self._audio_stream = None
        self._stream_end = False
        self._file = None
        self._memory_file = None

        encoded_filename = filename.encode(sys.getfilesystemencoding())

        self._file = ffmpeg_open_filename(encoded_filename)
        if not self._file:
            raise FFmpegException('Could not open "{0}"'.format(filename))

        self._video_stream_index = None
        self._audio_stream_index = None
        self._audio_format = None

        self.img_convert_ctx = POINTER(SwsContext)()
        self.audio_convert_ctx = POINTER(SwrContext)()

        file_info = ffmpeg_file_info(self._file)

        self.info = SourceInfo()
        self.info.title = file_info.title
        self.info.author = file_info.author
        self.info.copyright = file_info.copyright
        self.info.comment = file_info.comment
        self.info.album = file_info.album
        self.info.year = file_info.year
        self.info.track = file_info.track
        self.info.genre = file_info.genre

        # Pick the first video and audio streams found, ignore others.
        for i in range(file_info.n_streams):
            info = ffmpeg_stream_info(self._file, i)

            if isinstance(info, StreamVideoInfo) and \
                    self._video_stream is None:

                stream = ffmpeg_open_stream(self._file, i)

                self.video_format = VideoFormat(
                    width=info.width,
                    height=info.height)
                if info.sample_aspect_num != 0:
                    self.video_format.sample_aspect = (
                            float(info.sample_aspect_num) /
                            info.sample_aspect_den)
                self.video_format.frame_rate = (
                        float(info.frame_rate_num) /
                        info.frame_rate_den)
                self._video_stream = stream
                self._video_stream_index = i

            elif (isinstance(info, StreamAudioInfo) and
                  self._audio_stream is None):

                stream = ffmpeg_open_stream(self._file, i)

                self._audio_stream = stream
                self._audio_stream_index = i

                channel_input = self._get_default_channel_layout(
                    info.channels)
                channels_out = min(2, info.channels)
                channel_output = self._get_default_channel_layout(
                    channels_out)

                sample_rate = stream.codec_context.contents.sample_rate
                sample_format = stream.codec_context.contents.sample_fmt

                try:
                    sample_bits = self._AV_BITS[sample_format]
                except:
                    raise FFmpegException('Audio format not supported.')

                if not self.fixed_tgt_format:  # Automatic
                    if sample_bits == 32:
                        d = pyglet.media.get_audio_driver()
                        active_output = type(d).__name__.replace("Driver", "")
                        if AVAILABLE_AUDIO_OUTPUTS[active_output]["int32"]:
                            self.tgt_format = AV_SAMPLE_FMT_S32
                        elif AVAILABLE_AUDIO_OUTPUTS[active_output]["float32"]:
                            self.tgt_format = AV_SAMPLE_FMT_FLT
                        else:
                            self.tgt_format = AV_SAMPLE_FMT_S16
                    elif sample_bits == 16:
                        self.tgt_format = AV_SAMPLE_FMT_S16
                    elif sample_bits == 8:
                        self.tgt_format = AV_SAMPLE_FMT_U8
                elif self.fixed_tgt_format in self._AV_BITS:
                    self.tgt_format = self.fixed_tgt_format
                else:
                    raise FFmpegException('Audio format not supported.')

                self.audio_format = AudioFormat(
                    channels=channels_out,
                    sample_size=self._AV_BITS[self.tgt_format],
                    sample_rate=info.sample_rate)
                if self.tgt_format == AV_SAMPLE_FMT_FLT:
                    self.audio_format.sample_type = "float"
                else:
                    self.audio_format.sample_type = "int"

                self.audio_convert_ctx = self.get_formatted_swr_context(
                    channel_output, sample_rate, channel_input, sample_format)

                if (self._AV_BITS[self.tgt_format] < sample_bits):
                        res = avutil.av_opt_set(self.audio_convert_ctx,
                                                asbytes("dither_method"),
                                                asbytes("low_shibata"),
                                                0)
                        if res != 0:
                            print("Info: Bit reduction without dithering")

                if (not self.audio_convert_ctx or
                        swresample.swr_init(self.audio_convert_ctx) < 0):
                    swresample.swr_free(self.audio_convert_ctx)
                    raise FFmpegException(
                        'Cannot create sample rate converter.')

        self._packet = ffmpeg_init_packet()
        self._events = []  # They don't seem to be used!

        self.audioq = deque()
        # Make queue big enough to accomodate 1.2 sec?
        self._max_len_audioq = 50  # Need to figure out a correct amount
        if self.audio_format:
            # Buffer 1 sec worth of audio
            nbytes = ffmpeg_get_audio_buffer_size(self.audio_format)
            self._audio_buffer = (c_uint8 * nbytes)()

        self.videoq = deque()
        self._max_len_videoq = 50  # Need to figure out a correct amount

        self.start_time = self._get_start_time()
        self._duration = timestamp_from_ffmpeg(file_info.duration)
        self._duration -= self.start_time

        # Flag to determine if the _fillq method was already scheduled
        self._fillq_scheduled = False
        self._fillq()
        # Don't understand why, but some files show that seeking without
        # reading the first few packets results in a seeking where we lose
        # many packets at the beginning.
        # We only seek back to 0 for media which have a start_time > 0
        if self.start_time > 0:
            self.seek(0.0)

    def __del__(self):
        try:
            super().__del__()
        except:
            pass
        if platform.system() == "Windows" and self._tempfile:
            os.remove(self._tempfile.name)


class FFmpegDecoder(FFmpegDecoder):
    """Modified FFmpegDecoder to load modified FFmpegSource."""

    def decode(self, file, filename, streaming=True):
        return FFmpegSource(file, filename)


class AudioPlayer:
    """A class implementing an audio player.

    This is a wrapper around pyglet.media.Player.

    """

    available_audio_outputs = AVAILABLE_AUDIO_OUTPUTS
    available_output_formats = AVAILABLE_OUTPUT_FORMATS

    def __init__(self, audio_output, output_format):
        """Create an AudioPlayer object.

        Parameters
        ----------
        audio_output : str
            the pyglet audio driver to use ('XAudio2', 'DirectSound', 'OpenAL',
            'PulseAudio')
        audio_format : int
            the FFmpeg output format to use ("Automatic", "16-bit",
            "32-bit float")

        """

        audio_driver = self.available_audio_outputs[audio_output]["driver"]
        module = __import__(f"pyglet.media.drivers.{audio_driver}",
                            fromlist=['create_audio_driver'])
        pyglet.media.drivers._audio_driver = module.create_audio_driver()

        FFmpegSource.fixed_tgt_format = \
            self.available_output_formats[audio_output][output_format]

        self._audio_output = audio_output
        self._output_format = output_format
        self._player = pyglet.media.Player()
        self._on_eos = None
        self._clear_on_queue = True
        self.offset = 0
        print(f"Audio Output: {self.audio_output} ({self.output_format})")

    def __del__(self):
        """Delete an AudioPlayer object."""

        self._player.delete()

    @property
    def audio_output(self):
        return self._audio_output

    @property
    def output_format(self):
        return self._output_format

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
            source = pyglet.media.load(track.name, file=track,
                                       decoder=FFmpegDecoder())
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

    def __init__(self, audio_output, output_format):
        """Create an AudioPlayer object.

        Parameters
        ----------
        audio_output : str
            the pyglet audio driver to use ('XAudio2', 'DirectSound', 'OpenAL',
            'PulseAudio')
        audio_format : int
            the FFmpeg output format to use ("Automatic", "16-bit",
            "32-bit float")

        """

        super().__init__(audio_output, output_format)
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
            self._sourcegroup.add(pyglet.media.load(track.name, file=track,
                                                    decoder=FFmpegDecoder()))
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
