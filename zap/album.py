import os
import io
import re
import glob
import base64
import urllib
import struct
import zipfile
import tempfile
import datetime
import dateutil.parser
import multiprocessing
import xml.etree.ElementTree as ET

try:
    import mutagen
except ImportError:
    mutagen = None
    try:
        import tinytag
    except ImportError:
        tinytag = None
        try:
            import audio_metadata
        except ImportError:
            audio_metadata = None

import fitz

from .__init__ import __author__, __version__


FILETYPES = {"tracks": [".flac", ".opus"],
             "booklets":  [".pdf"],
             "images": [".jpeg", ".jpg", ".png"],
             "playlists": [".xspf"]}
SORT_IMAGES = True
STRICT_SLIDES = True    # True: show first booklet OR images OR default image
                        # False: show merged booklets AND images
ALT_ENCODINGS = True    # True: try alternative encodings of playlist filenames
                        #       to match wrongly encoded filenames in ZIP
                        # False: assume correct encoding of filenames in ZIP
FIX_TRACKNUMBERS = True # True: skip leading zeros in tracknumber tag and
                        #       assign succesive numbers if no tracknumber tag
                        # False: leave leading zeros in tracknumbers and omit
                        #        tracks without tracknumber tag
FIX_DATE = True         # True: try "year" tag if no "date" tag is found
                        # False: don't try "year" tag if no "date" tag is found

def _get_content(files):
    content = {"tracks": [],
               "booklets": [],
               "images": [],
               "playlists": []}
    for file in files:
        for types in FILETYPES:
            if os.path.splitext(file)[-1].lower() in FILETYPES[types]:
                if os.path.split(file)[0] == "":  # exclude subdirectories
                    content[types].append(file)
    return content

def _read_ogg_page(f):
    # Read the Ogg page header (27 bytes)
    header = f.read(27)
    if len(header) < 27:
        return None  # End of file or error

    # Unpack the header
    try:
        (capture_pattern, version, header_type, granule_position,
         serial_number, page_sequence_no, checksum, page_segments) = \
            struct.unpack('<4sBsqIIIB', header)
    except struct.error:
        raise ValueError("Not a valid Ogg file")

    # Check for the Ogg capture pattern
    if capture_pattern != b'OggS' or version != 0:
        raise ValueError("Not a valid Ogg file")

    # Read the segment table
    segment_table = f.read(page_segments)
    if len(segment_table) < page_segments:
        return None  # End of file or error

    # Read the segment data
    segment_sizes = [seg for seg in segment_table]
    body_size = sum(segment_sizes)
    body = f.read(body_size)

    return {'header': header, 'body': body, 'serial_number': serial_number,
            'granule_position': granule_position, 'header_type': header_type,
            'page_sequence_no': page_sequence_no,
            'page_segments': page_segments}

def _get_opus_stream_size(f):
    f.seek(0)
    header_count = 0
    serial = None
    size = 0
    last_page_size = None
    eos = False

    while True:
        page = _read_ogg_page(f)
        if page is None:
            break  # End of file or error
        # Read pages until first Opus header page (identification header)
        elif header_count == 0: # Identification header
            if page['body'][:8] != b'OpusHead':  # Page from other stream?
                continue
            else:  # Found it
                serial = page['serial_number']
                header_count += 1
        # Check for expected second Opus header page (comment header)
        elif header_count == 1 and page['serial_number'] == serial:
            if page['body'][:8] != b'OpusTags':
                raise ValueError("Not a valid Opus file")
            else:
                header_count += 1
        # Read pages until first page with audio data
        elif header_count == 2 and page['serial_number'] == serial:
            if int.from_bytes(page['header_type'], 'little') & 0x01:
                continue  # Contiunation of second Opus header page
            elif page['granule_position'] > 0:  # Found it
                header_count += 1
                last_page_size = len(page['body'])
                size += last_page_size
        # Read remaining pages with audio data
        elif page['granule_position'] > 0 and page['serial_number'] == serial:
            last_page_size = len(page['body'])
            size += last_page_size
            # If page is last page (end of stream), we are done
            if int.from_bytes(page['header_type'], 'little') & 0x04:
                eos = True
                break

    # If last page did not contain "end of stream" flag, it was incomplete
    if not eos:
        size -= last_page_size

    return size

def _get_track_metadata_audio_metadata(f):
    metadata = audio_metadata.loads(f.read())

    metadata["codec"] = re.findall(r'FLAC|Opus', type(metadata).__name__)[0]

    return metadata

def _get_track_metadata_tinytag(f):
    metadata = {"codec": "", "pictures": [], "streaminfo": {}, "tags":{}}
    tt = tinytag.TinyTag.get(file_obj=f, image=True)

    if type(tt).__name__ == "_Ogg":
        metadata["codec"] = "Opus"
    elif type(tt).__name__ == "_Flac":
        metadata["codec"] = "FLAC"

    if tt.images.any is not None:
        metadata["pictures"].append(tt.images.any)

    for tag in ["bit_depth", "bitrate", "channels", "duration", "sample_rate"]:
        if tag == "bitrate":
            if getattr(tt, tag) is not None:
                metadata["streaminfo"][tag] = getattr(tt, tag) * 1000
            else:
                try:
                    size = _get_opus_stream_size(f)
                except:
                    size = tt.filesize
                    for image in [tt.images.front_cover, tt.images.back_cover,
                                   tt.images.media, tt.images.other]:
                        if type(image) is tinytag.tinytag.Image:
                            size -= len(image.data)
                        elif type(image) is tinytag.tinytag.OtherImages:
                            for k in image:
                                for i in image[k]:
                                    size -= len(i.data)
                metadata["streaminfo"]["bitrate"] =  size * 8 / tt.duration
        else:
            if hasattr(tt, tag.replace("_", "")):
                metadata["streaminfo"][tag] = getattr(tt, tag.replace("_", ""))

    for tag in ["album", "albumartist", "artist", "date", "title",
                "tracknumber"]:
        if hasattr(tt, tag):
            metadata["tags"][tag] = [getattr(tt, tag)]
            if hasattr(tt, "other") and tag in tt.other:
                metadata["tags"][tag].extend(tt.other[tag])

    return metadata

def _get_track_metadata_mutagen(f):
    metadata = {"codec": "", "pictures": [], "streaminfo": {}, "tags":{}}
    m = mutagen.File(f)

    try:
        metadata["codec"] = re.findall(r'Opus|FLAC', type(m).__name__)[0]
    except:
        pass

    if hasattr(m, "pictures"):
        try:
            metadata["pictures"] = m.pictures
        except:
            pass
    elif "metadata_block_picture" in m.tags:
        try:
            b64_data = m.tags["metadata_block_picture"][0]
            data = base64.b64decode(b64_data)
            picture = mutagen.flac.Picture(data)
            metadata["pictures"] = [picture]
        except:
            pass

    for tag in ["bit_depth", "bitrate", "channels", "duration", "sample_rate"]:
        if tag == "bit_depth":
            if hasattr(m.info, "bits_per_sample"):
                metadata["streaminfo"][tag] = getattr(m.info,
                                                      "bits_per_sample")
        if tag == "bitrate":
            if hasattr(m.info, tag):
                metadata["streaminfo"][tag] = getattr(m.info, tag)
            else:
                try:
                    size = _get_opus_stream_size(f)
                except:
                    f.seek(0, os.SEEK_END)
                    total_size = f.tell()
                    metadata_size = sum(len(str(v).encode("utf-8")) \
                                        for v in m.tags.values())
                    size = total_size - metadata_size
                metadata["streaminfo"]["bitrate"] = size * 8 / m.info.length
        elif tag == "duration":
            metadata["streaminfo"][tag] = m.info.length
        elif tag == "sample_rate":
            if hasattr(m.info, tag):
                metadata["streaminfo"][tag] = getattr(m.info, tag)
            elif metadata["codec"] == "Opus":
                metadata["streaminfo"][tag] = 48000
        else:
            if hasattr(m.info, tag):
                metadata["streaminfo"][tag] = getattr(m.info, tag)

    for tag in ["album", "albumartist", "artist", "date", "title",
                "tracknumber"]:
        if tag in m.tags:
            metadata["tags"][tag] = m.tags[tag]

    return metadata

def _get_track_metadata(f):
    if mutagen is not None:
        return _get_track_metadata_mutagen(f)
    elif tinytag is not None:
        return _get_track_metadata_tinytag(f)
    elif audio_metadata is not None:
        return _get_track_metadata_audio_metadata(f)

def _sort_images(images):
    front = []
    back = []
    other = []
    for x in images:
        parts = re.split(r' |\_|\-|\.', os.path.splitext(x)[0])
        if "back" in parts:
            back.append(x)
        elif any(x in parts for x in ("front", "cover", "folder")):
            front.append(x)
        else:
            other.append(x)
    return tuple(front + other + back)

def _create_booklet_page(args):
    import fitz
    import io
    from PIL import Image
    pdf = fitz.open(args[0])
    page = pdf[args[1]]
    try:
        x, y = page.cropbox[2:]
    except:
        x, y = page.CropBox[2:]
    if x > y:
        factor = 2160 / x
    else:
        factor = 2160 / y
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(factor, factor))
        pix.pil_save(args[2], format="JPEG", optimize=True)
    except:
        pix = page.getPixmap(matrix=fitz.Matrix(factor, factor))
        pix.pillowWrite(args[2], format="JPEG", optimize=True)
    pdf.close()


def create_zipped_album(directory, filename=None):
    """Create a Zipped Album from a directory.

    Parameters
    ----------
    directory : str
        the path to the directory to create the Zipped Album from
    filename : str, optional
        the path to the file to save the Zipped Album to
        (if none is given, save as "<directory>.zlbm")

    Returns
    -------
    filename : str
        the path to the created Zipped Album file

    """

    if filename is None:
        filename = directory + ".zlbm"

    idx = 1
    orig_filename = filename
    while os.path.isfile(filename):
        name, ext = os.path.splitext(orig_filename)
        filename = f"{name} ({idx}){ext}"
        idx += 1

    assert os.path.isdir(directory)
    content = _get_content(os.listdir(directory))
    assert content["tracks"]
    with zipfile.ZipFile(filename, 'w') as archive:
        for file in (x for l in content.values() for x in l):
            archive.write(os.path.join(directory, file), arcname=file)

    return filename


class ZippedAlbum:
    """A class representing a Zipped Album."""

    def __init__(self, filename, exact=False):
        """Create a ZippedAlbum object.

        Parameters
        ----------
        filename : str
            the path to the Zipped Album file.
        exact : bool
            no image sorting, no strict slides, no trying alternative encodings

        """

        assert os.path.isfile(filename)

        self._filename = filename
        self._archive = zipfile.ZipFile(filename)
        self._tmpdir = tempfile.TemporaryDirectory()
        self._content = _get_content(sorted(self._archive.namelist()))
        self._sort_images = SORT_IMAGES
        self._strict_slides = STRICT_SLIDES
        self._alt_encodings = ALT_ENCODINGS
        self._fix_tracknumbers = FIX_TRACKNUMBERS
        self._fix_date = FIX_DATE
        assert self._content["tracks"]

        if exact:
            self._sort_images = False
            self._strict_slides = False
            self._alt_encodings = False
            self._fix_tracknumbers = False
            self._fix_date = False

    def __del__(self):
        if hasattr(self, "_archive"):
            self._archive.close()

        if hasattr(self, "_tmpdir"):
            self._tmpdir.cleanup()

    @property
    def filename(self):
        return self._filename

    @property
    def tracks(self):
        if hasattr(self, "_tracks"):
            return self._tracks
        else:
            self._tracks = {}
            for track in self._content["tracks"]:
                try:
                    with self._archive.open(track) as f:
                        self._tracks[track] = _get_track_metadata(f)
                        #self._archive.read(track))
                except:
                    pass
            return self._tracks

    @property
    def playlist(self):
        if hasattr(self, "_playlist"):
            return self._playlist
        else:
            playlist = {}
            if self._content["playlists"]:
                try:
                    root = ET.fromstring(
                        self._archive.read(self._content["playlists"][0]))
                    title = root.find("{http://xspf.org/ns/0/}title")
                    if title is not None:
                        if title.text:
                            playlist["title"] = title.text
                    creator = root.find("{http://xspf.org/ns/0/}creator")
                    if creator is not None:
                        if creator.text:
                            playlist["creator"] = creator.text
                    date = root.find("{http://xspf.org/ns/0/}date")
                    if date is not None:
                        if date.text:
                            try:
                                dateutil.parser.parse(date.text)
                                playlist["date"] = date.text
                            except:
                                pass
                    tracklist = root.find("{http://xspf.org/ns/0/}trackList")
                    if tracklist is not None and len(tracklist) > 0:
                        playlist["tracklist"] = []
                        for track in tracklist:
                            location = track.find(
                                "{http://xspf.org/ns/0/}location")
                            if location is not None:
                                if location.text:
                                    playlist["tracklist"].append(
                                        {"location": location.text})
                except:
                    pass
            self._playlist = playlist
            return self._playlist

    @property
    def title(self):
        if hasattr(self, "_title"):
            return self._title
        else:
            if "title" in self.playlist:
                self._title = self.playlist["title"]
            else:
                try:
                    album = [", ".join(v["tags"]["album"]) for k,v in \
                             self.tracks.items()]
                    if len(set(album)) > 1:
                        self._title = "Unknown Compilation"
                    elif album[0] == "":
                        self._title = "Unknown Album"
                    else:
                        self._title = album[0]
                except:
                    self._title = "Unknown Album"
            return self._title

    @property
    def artist(self):
        if hasattr(self, "_artist"):
            return self._artist
        else:
            if "creator" in self.playlist:
                self._artist = self.playlist["creator"]
            else:
                try:
                    artists = ["; ".join(v["tags"]["albumartist"]) \
                               for k,v in self.tracks.items()]
                except:
                    artists = []
                    for k,v in self.tracks.items():
                        try:
                            artists.append("; ".join(v["tags"]["artist"]))
                        except:
                            artists.append("Unknown Artist")
                if len(set(artists)) > 1:
                    self._artist = "Various Artists"
                else:
                    self._artist = artists[0]
            return self._artist

    @property
    def year(self):
        if hasattr(self, "_year"):
            return self._year
        else:
            if "date" in self.playlist:
                self._year = dateutil.parser.parse(self.playlist["date"]).year
            else:
                try:
                    date = []
                    for k,v in self.tracks.items():
                        try:
                            date.append(v["tags"]["date"])
                        except KeyError as e:
                            if self._fix_date:
                                date.append(v["tags"]["year"])
                            else:
                                raise e
                    lowest = 9999
                    highest = 0
                    for d in date:
                        for x in d:
                            try:
                                year = dateutil.parser.parse(x).year
                                if year > highest:
                                    highest = year
                                if year < lowest:
                                    lowest = year
                            except:
                                pass
                    if lowest > highest:
                        self._year = "Unknown Year"
                    if lowest == highest:
                        self._year = f"{highest}"
                    else:
                        self._year = f"{lowest}-{highest}"
                except:
                    self._year = "Unknown Year"
            return self._year

    @property
    def tracklist(self):
        if hasattr(self, "_tracklist"):
            return self._tracklist
        else:
            artists = []
            for k,v in self.tracks.items():
                try:
                    artists.append("; ".join(v["tags"]["artist"]))
                except:
                    artists.append("Unknown Artist")
            tracklist = []
            if "tracklist" in self.playlist:
                for c,x in enumerate(self.playlist["tracklist"]):
                    filename = x["location"]
                    try:
                        track = self.tracks[filename]
                    except:
                        if self._alt_encodings:
                            import pkgutil
                            import encodings
                            false_positives = set(["aliases"])
                            encodings = set(
                                name for imp, name, ispkg in \
                                pkgutil.iter_modules(
                                    encodings.__path__) if not ispkg)
                            encodings.difference_update(false_positives)
                            encodings = list(encodings)
                            encodings.insert(0, encodings.pop(encodings.index(
                                "latin_1")))
                            encodings.insert(0, encodings.pop(encodings.index(
                                "cp1252")))
                            encodings.insert(0, encodings.pop(encodings.index(
                                "utf_8")))
                            continue_ = True
                            for encoding in encodings: #("utf-8", "cp1252"):
                                try:
                                    filename = filename.encode(
                                        encoding).decode("cp437")
                                    track = self.tracks[filename]
                                    continue_ = False
                                    break
                                except:
                                    pass
                            if continue_:
                                continue
                        else:
                            continue
                    #d = datetime.timedelta(
                    #    seconds=track["streaminfo"]["duration"])
                    #d = str(d - datetime.timedelta(
                    #    microseconds=d.microseconds))
                    #duration = d.lstrip("0:")
                    total_minutes = int(track["streaminfo"]["duration"] / 60)
                    total_seconds = round(track["streaminfo"]["duration"] % 60)
                    duration = f"{total_minutes}:{total_seconds:02}"

                    if len(set(artists)) > 1:
                        try:
                            artist = "; ".join(track["tags"]["artist"])
                        except:
                            artist = "Unknown Artist"
                        try:
                            title = "; ".join(track["tags"]["title"])
                        except:
                            title = "Unknown Title"
                        name = f"{artist} - {title}"
                        if name == "Unknown Artist - Unknown Title":
                            name = os.path.splitext(filename)[0]
                    else:
                        try:
                            name = "; ".join(track["tags"]["title"])
                        except:
                            name = os.path.splitext(filename)[0]
                    track["display"] = [str(c + 1), name, duration]
                    track["filename"] = filename
                    tracklist.append(track)
            else:
                used_numbers = []
                for nr, (filename, track) in enumerate(self.tracks.items()):

                    #d = datetime.timedelta(
                    #    seconds=track["streaminfo"]["duration"])
                    #d = str(d - datetime.timedelta(
                    #    microseconds=d.microseconds))
                    #d = d.split(":")
                    #if int(d[0]) > 0:
                    #    duration = ":".join(d)
                    #else:
                    #    if int(d[1]) <= 9:
                    #        d[1] = d[1][1:]
                    #    duration = ":".join(d[1:])
                    total_minutes = int(track["streaminfo"]["duration"] / 60)
                    total_seconds = round(track["streaminfo"]["duration"] % 60)
                    duration = f"{total_minutes}:{total_seconds:02}"

                    if len(set(artists)) > 1:
                        try:
                            artist = "; ".join(track["tags"]["artist"])
                        except:
                            artist = "Unknown Artist"
                        try:
                            title = "; ".join(track["tags"]["title"])
                        except:
                            title = "Unknown Title"
                        name = f"{artist} - {title}"
                        if name == "Unknown Artist - Unknown Title":
                            name = os.path.splitext(filename)[0]
                    else:
                        try:
                            name = "; ".join(track["tags"]["title"])
                        except:
                            name = os.path.splitext(filename)[0]
                    try:
                        numbers = track["tags"]["tracknumber"]
                        used_numbers.extend(numbers)
                    except:
                        if self._fix_tracknumbers:
                            for x in range(nr + 1):
                                if not str(x + 1) in used_numbers:
                                    numbers = [str(x + 1)]
                                    used_numbers.append(str(x + 1))
                                    break
                        else:
                            continue
                    for number in numbers:
                        if self._fix_tracknumbers:
                            try:
                                number = str(int(number))
                            except:
                                pass
                        track["display"] = [number, name, duration]
                        track["filename"] = filename
                        tracklist.append(track)
                tracklist = tuple(sorted(tracklist,
                                         key=lambda x: int(x["display"][0])))
            self._tracklist = tracklist
            return self._tracklist

    @property
    def playtime(self):
        if hasattr(self, "_playtime"):
            return self._playtime
        else:
            durations = [x["streaminfo"]["duration"] for x in self.tracklist]
            #d = datetime.timedelta(seconds=sum(durations))
            #d = str(d - datetime.timedelta(microseconds=d.microseconds))
            #d = d.split(":")
            #if int(d[0]) > 0:
            #    self._playtime = ":".join(d)
            #else:
            #    if int(d[1]) < 9:
            #        d[1] = d[1][1:]
            #    self._playtime = ":".join(d[1:])
            total_seconds = round(sum(durations))
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours == 0:
                self._playtime = f"{minutes}:{seconds:02}"
            else:
                self._playtime = f"{hours}:{minutes:02}:{seconds:02}"
            return self._playtime

    @property
    def nr_of_slides(self):
        if hasattr(self, "_nr_of_slides"):
            return self._nr_of_slides
        else:
            if self._content["booklets"]:
                booklet = fitz.open(self._booklet_path)
                booklet_pages = len(booklet)
                booklet.close()
            else:
                booklet_pages = 0
            images = self._content["images"]
            if self._strict_slides:
                if booklet_pages > 0:
                    self._nr_of_slides = booklet_pages
                else:
                    self._nr_of_slides = len(images)
            else:
                self._nr_of_slides = booklet_pages + len(images)
            return self._nr_of_slides

    def get_audio(self, nr):
        """Get the audio of a track in the Zipped Album.

        Parameters
        ----------
        nr : int
            the track number to get the audio from

        Returns
        -------
        audio : zipfile.ZipExtFile object
            a binary file-like object holding the audio information

        """

        try:
            return self._archive.open(self.tracklist[nr]["filename"])
        except:
            pass

    def get_slide(self, nr):
        """Get a slide from the booklet.

        Parameters
        ----------
        nr : int
            the number of the slide to get

        Returns
        -------
        slide : io.BytesIO
            a file-like object holding the slide information

        """

        if nr is None:
            nr = 0
        if nr < 0 or nr > self.nr_of_slides:
            return False

        elif self.nr_of_slides == 0:
            return os.path.abspath(os.path.join(
            os.path.split(__file__)[0], "unknown_album.png"))

        if self._strict_slides:
            if self._content["booklets"]:
                booklet_pages = self.nr_of_slides
            else:
                booklet_pages = 0
        else:
            booklet_pages = self.nr_of_slides - len(self._content["images"])
        if nr < booklet_pages:
            filename = os.path.join(self._tmpdir.name, f"{nr}.jpg")
            if os.path.isfile(filename):
                return filename
            else:
                return None
        else:
            nr -= booklet_pages
            if self._sort_images:
                images = _sort_images(self._content["images"])
            else:
                images = self._content["images"]
            return io.BytesIO(self._archive.read(images[nr]))

    def prepare_booklet_pages(self, cover_ready_callback=None):
        """Prepare booklet pages in separate thread.

        Parameters
        ----------
        cover_ready_callback : function
            a function to be called when the first page has been prepared

        """

        if self._content["booklets"]:
            self._booklet_path = None
            try:
                booklet = fitz.open(
                    stream=self._archive.read(self._content["booklets"][0]),
                    filetype="pdf")
                if not self._strict_slides and \
                        len(self._content["booklets"]) > 1:
                    for other in self._content["booklets"][1:]:
                        doc = fitz.open(stream=self._archive.read(other),
                                        filetype="pdf")
                        try:
                            booklet.insert_pdf(doc)
                        except:
                            booklet.insertPDF(doc)
                        doc.close()
                path = os.path.join(self._tmpdir.name, "booklet.pdf")
                booklet.save(path)
                nr_pages = len(booklet)
                booklet.close()
                self._booklet_path = path

                # Prepare first page (cover image)
                pool = multiprocessing.Pool()
                pool.apply_async(_create_booklet_page,
                                 ([self._booklet_path, 0,
                                   os.path.join(self._tmpdir.name, "0.jpg")],),
                                 callback=cover_ready_callback)

                # Prepare other pages
                page_numbers = []
                filepaths = []
                for p in range(1, nr_pages):
                    page_numbers.append(p)
                    filepaths.append(os.path.join(self._tmpdir.name,
                                                  f"{p}.jpg"))
                func_args = zip([self._booklet_path] * len(page_numbers),
                                page_numbers, filepaths)
                pool.map_async(_create_booklet_page, func_args)

            except:
                pass
