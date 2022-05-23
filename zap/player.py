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

try:
    assert pyglet.media.codecs.have_ffmpeg()
except:
    raise RuntimeError("Error loading FFmpeg shared libraries!")

from pyglet.media.codecs.ffmpeg import *
pyglet.options['audio'] = ('openal', 'directsound', 'silent')

from .__meta__ import __author__, __version__


class FFmpegSource(FFmpegSource):
    """Modified FFmpegSource with some fixes.

    Fixes:
        - Close tempfile after writing it
        - Delete tempfile when object is deleted
        - Allow bit depth to be higher than 16
        - Reduce bit rate to 16 when using OpenAL
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
        self._file = None

        self._file = ffmpeg_open_filename(asbytes_filename(filename))
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
                  info.sample_bits in [8, 16, 32] and
                  self._audio_stream is None):

                stream = ffmpeg_open_stream(self._file, i)

                self._audio_stream = stream
                self._audio_stream_index = i

                channel_input = avutil.av_get_default_channel_layout(
                    info.channels)
                channels_out = min(2, info.channels)
                channel_output = avutil.av_get_default_channel_layout(
                    channels_out)

                bitdepth = info.sample_bits
                bitreduction = False
                sample_rate = stream.codec_context.contents.sample_rate
                sample_format = stream.codec_context.contents.sample_fmt
                if sample_format in (AV_SAMPLE_FMT_U8, AV_SAMPLE_FMT_U8P):
                    self.tgt_format = AV_SAMPLE_FMT_U8
                elif sample_format in (AV_SAMPLE_FMT_S16, AV_SAMPLE_FMT_S16P):
                    self.tgt_format = AV_SAMPLE_FMT_S16
                elif sample_format in (AV_SAMPLE_FMT_S32, AV_SAMPLE_FMT_S32P):
                    if type(pyglet.media.get_audio_driver()).__name__ == \
                            "OpenALDriver":
                        self.tgt_format = AV_SAMPLE_FMT_S16
                        bitdepth = 16
                        bitreduction = True
                    else:
                        self.tgt_format = AV_SAMPLE_FMT_S32
                elif sample_format in (AV_SAMPLE_FMT_FLT, AV_SAMPLE_FMT_FLTP):
                    self.tgt_format = AV_SAMPLE_FMT_S16
                else:
                    raise FFmpegException('Audio format not supported.')

                self.audio_format = AudioFormat(
                    channels=channels_out,
                    sample_size=bitdepth,
                    sample_rate=info.sample_rate)

                self.audio_convert_ctx = swresample.swr_alloc_set_opts(
                    None, channel_output, self.tgt_format, sample_rate,
                    channel_input, sample_format, sample_rate, 0, None)

                if bitreduction and avutil.av_opt_set(self.audio_convert_ctx,
                                                      asbytes("dither_method"),
                                                      asbytes("low_shibata"),
                                                      0) != 0:
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
        super().__del__()
        if platform.system() == "Windows" and self._tempfile:
            os.remove(self._tempfile.name)


class FFmpegDecoder(FFmpegDecoder):
    """Modified FFmpegDecoder to load modified FFmpegSource."""

    def decode(self, file, filename, streaming=True):
        return FFmpegSource(filename, file)


class AudioPlayer:
    """A class implementing an audio player.

    This is a wrapper around pyglet.media.Player.

    """

    def __init__(self):
        """Create an AudioPlayer object."""

        self._player = pyglet.media.Player()
        self._on_eos = None
        self._clear_on_queue = True
        print(f"Audio playback: {self.audio_driver}")

    def __del__(self):
        """Delete an AudioPlayer object."""

        self._player.delete()

    @property
    def audio_driver(self):
        return type(pyglet.media.get_audio_driver()).__name__

    @property
    def is_playing(self):
        return self._player.playing

    @property
    def buffer_size(self):
        if self.is_playing:
            if self.audio_driver == "DirectSoundDriver":
                return self._player._audio_player._buffer_size
            elif self.audio_driver == "OpenALDriver":
                return self._player._audio_player.ideal_buffer_size

    @property
    def buffer_time(self):
        if self.is_playing:
            rate = self._player._audio_player.source.audio_format.sample_rate
            size = self._player._audio_player.source.audio_format.sample_size
            channels = self._player._audio_player.source.audio_format.channels
            return self.buffer_size / rate / (size / 8 * channels)

    @property
    def time(self):
        return self._player.time

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

    def __init__(self):
        super().__init__()
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
                current_duration = self._current_duration
                super().seek(time)

    def update(self):
        """Update the audio player."""

        if self._sourcegroup._sources != []:
            if self._current_duration is not None:
                if self._sourcegroup._advanced:
                    self._sourcegroup._advanced = False
                    self._on_gapless_eos()
                if self.time > self._current_duration:
                    if len(self._sourcegroup._sources) > 0:
                        self._player._timer.set_time(self.time - \
                                                     self._current_duration)
                        self._current_duration = \
                            self._sourcegroup._sources[0].duration
                    else:
                        self._current_duration = None
        else:
            self._on_eos()
