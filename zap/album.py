import os
import io
import glob
import urllib
import zipfile
import tempfile
import datetime
import dateutil.parser
import multiprocessing
import xml.etree.ElementTree as ET

import audio_metadata
import fitz

from .__meta__ import __author__, __version__


FILETYPES = {"tracks": [".flac", ".opus"],
             "booklets":  [".pdf"],
             "images": [".jpeg", ".jpg", ".png"],
             "playlists": [".xspf"]}
SORT_IMAGES = True
STRICT_SLIDES = True  # True: show first booklet OR images OR default image
                      # False: show merged booklets AND images

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

def _sort_images(images):
    front = []
    back = []
    other = []
    for x in images:
        if os.path.splitext(x)[0].endswith("folder") or \
                os.path.splitext(x)[0].endswith("cover") or \
                os.path.splitext(x)[0].endswith("front"):
            front.append(x)
        elif os.path.splitext(x)[0].endswith("back"):
            back.append(x)
        else:
            other.append(x)
    return tuple(front + other + back)

def _create_booklet_page(args):
    import fitz
    import io
    from PIL import Image
    pdf = fitz.open(args[0])
    page = pdf[args[1]]
    x, y = page.CropBox[2:]
    if x > y:
        factor = 2160 / x
    else:
        factor = 2160 / y
    pix = page.getPixmap(matrix=fitz.Matrix(factor, factor))
    pix.pillowWrite(args[2], format="JPEG", optimize=True)
    pdf.close()


class ZippedAlbum:
    """A class representing a Zipped Album."""

    def __init__(self, filename):
        """Create a ZippedAlbum object.

        Parameters
        ----------
        filename : str
            the path to the Zipped Album file.

        """

        assert os.path.isfile(filename)

        self._filename = filename
        self._archive = zipfile.ZipFile(filename)
        self._tmpdir = tempfile.TemporaryDirectory()
        self._content = _get_content(sorted(self._archive.namelist()))

        assert self._content["tracks"]

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
                    self._tracks[track] = audio_metadata.loads(
                        self._archive.read(track))
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
                    artist = ["; ".join(v["tags"]["albumartist"]) \
                              for k,v in self.tracks.items()]
                except:
                    try:
                        artist = ["; ".join(v["tags"]["artist"]) \
                                  for k,v in self.tracks.items()]
                    except:
                        artist = ["Unknown Artist"]
                if len(set(artist)) > 1:
                    self._artist = "Various Artists"
                else:
                    self._artist = artist[0]
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
                    date = [v["tags"]["date"] for k,v in self.tracks.items()]
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
            tracklist = []
            if "tracklist" in self.playlist:
                tracks = [self.tracks[x["location"]] \
                          for x in self.playlist["tracklist"]]
                for c,x in enumerate(self.playlist["tracklist"]):
                    filename = x["location"]
                    track = self.tracks[filename]
                    d = datetime.timedelta(
                        seconds=track["streaminfo"]["duration"])
                    d = str(d - datetime.timedelta(
                        microseconds=d.microseconds))
                    duration = d.lstrip("0:")
                    try:
                        if self.artist == "Various Artists":
                            artist = "; ".join(track["tags"]["artist"])
                            title = "; ".join(track["tags"]["title"])
                            name = f"{artist} - {title}"
                        else:
                            name = "; ".join(track["tags"]["title"])
                    except:
                        name = filename
                    track["display"] = [str(c + 1), name, duration]
                    tracklist.append(track)
            else:
                for nr, (filename, track) in enumerate(self.tracks.items()):
                    d = datetime.timedelta(
                        seconds=track["streaminfo"]["duration"])
                    d = str(d - datetime.timedelta(
                        microseconds=d.microseconds))
                    d = d.split(":")
                    if int(d[0]) > 0:
                        duration = ":".join(d)
                    else:
                        if int(d[1]) < 9:
                            d[1] = d[1][1:]
                        duration = ":".join(d[1:])
                    try:
                        if self.artist == "Various Artists":
                            artist = "; ".join(track["tags"]["artist"])
                            title = "; ".join(track["tags"]["title"])
                            name = f"{artist} - {title}"
                        else:
                            name = "; ".join(track["tags"]["title"])
                    except:
                        name = filename
                    try:
                        numbers = track["tags"]["tracknumber"]
                    except:
                        numbers = [str(nr)]
                    for number in numbers:
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
            d = datetime.timedelta(seconds=sum(durations))
            d = str(d - datetime.timedelta(microseconds=d.microseconds))
            d = d.split(":")
            if int(d[0]) > 0:
                self._playtime = ":".join(d)
            else:
                if int(d[1]) < 9:
                    d[1] = d[1][1:]
                self._playtime = ":".join(d[1:])
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
            if STRICT_SLIDES:
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

        return self._archive.open(self.tracklist[nr]["filename"])

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

        if STRICT_SLIDES:
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
            if SORT_IMAGES:
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
                if not STRICT_SLIDES and len(self._content["booklets"]) > 1:
                    for other in self._content["booklets"][1:]:
                        doc = fitz.open(stream=self._archive.read(other),
                                        filetype="pdf")
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
