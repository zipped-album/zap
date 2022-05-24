# -*- coding: utf-8 -*-

"""ZAP

Zipped Album Player.

"""


import os
import io
import gc
import sys
import copy
import time
import random
import colorsys
import platform
import dateutil.parser
try:
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.font as tkfont
    from tkinter import scrolledtext
    from tkinter import filedialog
    from tkinter import messagebox
except ImportError:
    print("Error: Tkinter not found!")
except ModuleNotFoundError:
    print("Error: Python not configured for Tk!")
    sys.exit()

from PIL import ImageTk, Image

from .__meta__ import __author__, __version__
from .album import ZippedAlbum, create_zipped_album
from .binaries import has_ffmpeg, download_ffmpeg, get_platform


if "--SCALING" in sys.argv:
    SCALING = float(sys.argv[sys.argv.index("--SCALING") + 1])
elif "GDK_SCALE" in os.environ:
    SCALING = float(os.environ["GDK_SCALE"])
elif "QT_SCREEN_SCALE_FACTORS" in os.environ:
    SCALING = float(os.environ["QT_SCREEN_SCALE_FACTORS"].split(
        ";")[0].split("=")[-1])
else:
    SCALING = 1

WIDTH = int(1024 * SCALING)
HEIGHT = int(600 * SCALING)
PADDING = int(8 * SCALING)
CELLPADDING = int(8 * SCALING) #8=2x4 cell padding
if platform.system() == "Windows":
    FONTNAME = "Calibri"
    FONTSIZE = 11
elif platform.system() == "Darwin":
    FONTNAME = "Helvetica Neue"
    FONTSIZE =13
else:
    FONTNAME = "Nimbus Sans"
    FONTSIZE = 10

ABOUT_TEXT = """
 ╔═══════════════════════════════════ ZAP ═══════════════════════════════════╗
 ║                                                                           ║
 ║                       Zipped Album Player (v {ver})                       ║
 ║                                                                           ║
 ║                by Florian Krause <florian.krause@fladd.de>                ║
 ║                                                                           ║
 ╚═══════════════════════════════════════════════════════════════════════════╝

 ┌──── Keyboard navigation ──────────────────────────────────────────────────┐
 │                                                                           │
 │  Play/Pause: ............................. Space ......... or ... Return  │
 │  Select next track: ...................... Down .......... or ........ j  │
 │  Select previous track: .................. Up ............ or ........ k  │
 │  Select first track: ..................... Home .......... or ....... gg  │
 │  Select last track: ...................... End ........... or ........ G  │
 │  Seek forward: ........................... Right ......... or ........ l  │
 │  Seek backward: .......................... Left .......... or ........ h  │
 │  Seek to beginning: ...................... w ............. or ........ 0  │
 │  Show next slide: ........................ Shift+Right ... or ........ L  │
 │  Show previous slide: .................... Shift+Left .... or ........ H  │
 │  Show first slide: ....................... W ............. or ........ )  │
 │  Decrease volume: ........................ Shift+Down .... or ........ J  │
 │  Increase volume: ........................ Shift+Up....... or ........ K  │
 │                                                                           │
 └───────────────────────────────────────────────────────────────────────────┘
""".format(ver=__version__)

UPDATE_INTERVALL = 100  # in ms

while True:
    h,l,s = [random.random() for x in range(3)]
    if 0.4 <= l <= 0.7:
        r,g,b = [int(x * 255) for x in colorsys.hls_to_rgb(h,l,s)]
        COLOUR = f"#{r:02X}{g:02X}{b:02X}"
        break

def _create_frame(self, x, y, r, **kwargs):
    return self.create_rectangle(x-r, y-r, x+r, y+r, **kwargs)
tk.Canvas.create_frame = _create_frame

def _frame_coords(self, frame_id, x, y, r):
    self.coords(frame_id, x-r, y-r, x+r, y+r)
tk.Canvas.frame_coords = _frame_coords

def get_shaded_colour(rgb, amount):
        h,l,s = colorsys.rgb_to_hls(rgb[0], rgb[1], rgb[2])
        l = amount
        r,g,b = [int(x * 255) for x in colorsys.hls_to_rgb(h,l,s)]
        colour = f"#{r:02X}{g:02X}{b:02X}"
        return colour


class AutoScrollbar(ttk.Scrollbar):
    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        ttk.Scrollbar.set(self, lo, hi)


class ResizingCanvas(tk.Canvas):
    def __init__(self,parent, **kwargs):
        tk.Canvas.__init__(self, parent, **kwargs)
        self.bind("<Configure>", self.on_resize)
        self.height = self.winfo_reqheight()
        self.width = self.winfo_reqwidth()

    def on_resize(self, event):
        # determine the ratio of old width/height to new width/height
        wscale = float(event.width) / self.width
        hscale = float(event.height) / self.height
        self.width = event.width
        self.height = event.height
        # resize the canvas 
        self.config(width=self.width, height=self.height)
        # rescale all the objects tagged with the "all" tag
        self.scale("all", 0, 0, wscale, hscale)


class TrackTooltip:
    def __init__(self, treeview):
        self.treeview = treeview
        self.album = None
        self.tooltip_window = None
        self.tooltip_x = self.tooltip_y = 0
        self.last_idd = None
        self.waittime = 1000
        self.id = None

        self.style = ttk.Style()
        def fixed_map(option):
            # Fix for setting text colour for Tkinter 8.6.9
            # From: https://core.tcl.tk/tk/info/509cafafae
            #
            # Returns the style map for 'option' with any styles starting with
            # ('!disabled', '!selected', ...) filtered out.

            # style.map() returns an empty list for missing options, so this
            # should be future-safe.
            return [elm for elm in self.style.map('Treeview', query_opt=option)
                    if elm[:2] != ('!disabled', '!selected')]
        self.style.map('Treeview', foreground=fixed_map('foreground'),
                       background=fixed_map('background'))

        self.treeview.bind("<Motion>", self.schedule)
        self.treeview.bind("<Leave>", self.leave)

    def schedule(self, event):
        self.unschedule()
        idd = self.treeview.identify_row(event.y)
        if not idd:
            if self.tooltip_window:
                self.hide()
            return
        if idd == self.last_idd:
            return
        if self.tooltip_window:
            self.hide()
            return
        self.id = self.treeview.after(self.waittime, lambda: self.show(event))

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.treeview.after_cancel(id)

    def show(self, event):
        idd = self.treeview.identify_row(event.y)
        if idd == "":
            return
        self.tooltip_window = tk.Toplevel(self.treeview, highlightthickness=1,
                                          bg="white")
        rgb = [x / 65535 for x in self.tooltip_window.winfo_rgb(
            self.style.lookup('TFrame', 'background'))]
        highlight_colour = get_shaded_colour(rgb, 0.52)
        self.tooltip_window["highlightbackground"] = highlight_colour
        self.tooltip_window.wm_overrideredirect(1)
        self.tooltip_window.columnconfigure(2, weight=1)
        track = self.album.tracklist[int(idd)]
        tags = track["tags"].keys()
        if track["pictures"] != []:
            im = Image.open(io.BytesIO(track["pictures"][0].data))
        else:
            im = Image.open(self.album.get_slide(0))
        im = im.resize((100, 100), Image.ANTIALIAS)
        self.photo = ImageTk.PhotoImage(im)
        im.close()
        label = tk.Label(self.tooltip_window, image=self.photo,
                         bg=COLOUR,
                         borderwidth=0, highlightthickness = 0, padx=0, pady=0)
        label.grid(row=0, column= 0, sticky="nw")
        self.frame = ttk.Frame(self.tooltip_window)
        self.frame.columnconfigure(0, minsize=200)
        self.frame.grid(column=1, row=0, sticky="nesw")
        try:
            title = "; ".join(track["tags"]["title"])
        except:
            title = "Unknown Title"
        label = ttk.Label(self.frame, text=title, justify=tk.LEFT,
                          font=(FONTNAME, FONTSIZE-2, "bold"),
                          wraplength=self.treeview.winfo_width() - 120)
        label.grid(row=0, column= 0, padx=2, ipadx=0, ipady=0, sticky="nw")
        try:
            artist = "; ".join(track["tags"]["artist"])
        except:
            artist = "Unknown Artist"
        label = ttk.Label(self.frame,
                          text=artist, justify=tk.LEFT,
                          font=(FONTNAME, FONTSIZE-2, "italic"),
                          wraplength=self.treeview.winfo_width() - 120)
        label.grid(row=1, column= 0, padx=2, ipadx=0, ipady=0, sticky="nw")
        try:
            try:
                year = "; ".join([str(dateutil.parser.parse(x).year) \
                                  for x in track["tags"]["date"]])
            except KeyError as e:
                if self.album._fix_date:
                    year = "; ".join([str(dateutil.parser.parse(x).year) \
                                      for x in track["tags"]["year"]])
                else:
                    raise e
        except:
            year = "Unknown Year"
        label = ttk.Label(self.frame, text=year, justify=tk.LEFT,
                          font=(FONTNAME, FONTSIZE-2),
                          wraplength=self.treeview.winfo_width() - 120)
        label.grid(row=2, column= 0, padx=2, ipadx=0, ipady=0, sticky="nw")

        x, y, cx, cy = self.treeview.bbox(idd)
        x = x + self.treeview.winfo_rootx() + event.x + 15
        rowheight = self.style.lookup("Treeview", "rowheight")
        if rowheight == "":
            rowheight = 20
        y = y + cy + self.treeview.winfo_rooty() - rowheight // 2 - 50
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        try:
            # For Mac OS
            self.tooltip_window.tk.call("::tk::unsupported::MacWindowStyle",
                                         "style", self.tooltip_window._w,
                                         "help", "noActivates")
        except tk.TclError:
            pass

        self.tooltip_window.update()
        try:
            self.tooltip_window.lift()  # work around bug in Tk 8.5.18+
        except:
            pass

        self.last_idd = idd

    def leave(self, event):
        self.unschedule()
        self.hide()

    def hide(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None
        self.last_idd = None


class HelpDialogue:
    def __init__(self, master):
        self.master = master
        top = self.top = tk.Toplevel(master)
        top.title("About")
        top.resizable(False, False)

        self.text = tk.Text(top, width=79, height=len(ABOUT_TEXT.split("\n")))
        self.text.pack(expand=True, fill="both")
        self.text.insert(tk.END, ABOUT_TEXT)
        self.text["state"] = "disabled"

        top.protocol("WM_DELETE_WINDOW", self.ok)
        top.bind("<Escape>", self.ok)

        top.geometry("+%d+%d" % (master.winfo_rootx(), master.winfo_rooty()))

        top.transient(self.master)
        top.focus_force()
        top.wait_visibility()
        top.grab_set()
        if platform.system() == "Windows":
            master.wm_attributes("-disabled", True)
        master.wait_window(top)

    def ok(self, *args):
        if platform.system() == "Windows":
            self.master.wm_attributes("-disabled", False)
        self.top.grab_release()
        self.top.destroy()


class DownloadFFmpegDialogue:
    def __init__(self, master):
        self.master = master
        top = self.top = tk.Toplevel(master)
        top.title("Downloading...")
        top.resizable(False, False)

        self.text1 = ttk.Label(top, text="", anchor=tk.CENTER)
        self.text1.grid(row=0, column=0, sticky="nesw")
        self.progressbar = ttk.Progressbar(top, length=WIDTH, maximum=100)
        self.progressbar.grid(row=1, column=0, sticky="nesw")
        self.text2 = ttk.Label(top, text="", anchor=tk.CENTER)
        self.text2.grid(row=2, column=0, sticky="nesw")

        top.protocol("WM_DELETE_WINDOW", lambda: None)

        root_x = int(master.parent.geometry().split("+", 1)[-1].split("+")[0])
        top.geometry(f"+%d+%d" % (root_x, master.winfo_rooty()))

        top.transient(self.master)
        top.focus_force()
        top.wait_visibility()
        top.grab_set()
        if platform.system() == "Windows":
            master.parent.wm_attributes("-disabled", True)

    def start(self, *args):
        def _progress(count, total, message=''):
            """Progress callback function"""

            percents = int(100.0 * count / float(total))
            self.progressbar["value"] = percents
            self.text1["text"] = message
            self.text2["text"] = f"{percents} %"
            self.top.update()

        try:
            download_ffmpeg(_progress)
            self.destroy()
            messagebox.showinfo(title="Done",
                                message="FFmpeg libraries have been "
                                "downloaded successfully!")
        except Exception as e:
            try:
                if e.status == 404:
                    self.destroy()
                    platform = get_platform()
                    messagebox.showerror(title="No download available",
                                         message="There is no download "
                                         "available for this platform "
                                         f"({platform})!\n\n"
                                         "Please manually install FFmpeg "
                                         "libraries (version 4) on your "
                                         "system.")
                else:
                    raise Exception
            except Exception:
                if messagebox.askretrycancel(title="Download failed",
                                             message="The download has failed "
                                             "for an unknown reason!",
                                             icon="error"):
                    self.start()
                else:
                    self.destroy()

    def destroy(self, *args):
        if platform.system() == "Windows":
            self.master.parent.wm_attributes("-disabled", False)
        self.top.grab_release()
        self.top.destroy()


class MainApplication(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.style = ttk.Style()
        self.size = [WIDTH, HEIGHT]
        self.repeat_album = tk.BooleanVar()
        self.repeat_album.set(False)
        self.create_menu()
        self.create_widgets()
        self.remove_arrows()
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)
        self.always_on_top = False
        self.fullscreen = False
        #self.create_bindings()
        self.loaded_album = None
        self.current_image = None
        self.selected_track_id = None
        self.playing_track_id = None
        self.resize_after_id = None
        self.last_update_player = 0
        self.now = time.monotonic

        def update_player():
            try:
                if hasattr(self, "player") and self.player.is_playing:
                    self.player.update()
                    now = self.now()
                    if now - self.last_update_player >= 1:
                        track = self.loaded_album.tracklist[
                            self.selected_track_id]
                        time = self.player.time
                        if str(self.playpause_button["state"]) == "normal":
                            playhead = 100 / track["streaminfo"]["duration"] \
                                * time
                            self.playhead = playhead
                        self.last_update_player = now
                self.after(UPDATE_INTERVALL, update_player)
            except tk._tkinter.TclError:
                pass

        update_player()

    @property
    def volume(self):
        return self.volume_slider["value"]

    @volume.setter
    def volume(self, value):
        if 0 <= value <= self.volume_slider["maximum"]:
            self.volume_slider["value"] = value
            self.volume_label["text"] = f"Vol: {str(int(value)).rjust(3)}"
            if hasattr(self, "player"):
                self.player.volume = value / 100

    @property
    def playhead(self):
        return self.playhead_slider["value"]

    @playhead.setter
    def playhead(self, value):
        if value is None:
            self.playhead_label["text"] = ""
        else:
            if 0 <= value <= self.playhead_slider["maximum"]:
                self.playhead_slider["value"] = value
                track = self.loaded_album.tracklist[self.selected_track_id]
                total_minutes = int(track["streaminfo"]["duration"] / 60)
                total_seconds = int(track["streaminfo"]["duration"] % 60)
                pad_minutes = len(str(total_minutes))
                pos = track["streaminfo"]["duration"] / 100 * self.playhead
                minutes = int(pos / 60)
                seconds = int(pos % 60)
                min_str = str(minutes).rjust(pad_minutes, '0')
                sec_str = str(seconds).rjust(2, '0')
                self.playhead_label["text"] = f"{min_str}:{sec_str}"

    def _open_album(self, *args, **kwargs):
        if "exact" in kwargs:
            exact = True
        else:
            exact = False
        if self.loaded_album is not None:
            initialdir = os.path.split(self.loaded_album.filename)[0]
        else:
            initialdir = os.getcwd()
        allowed_extensions = "*.zip *.zlbm"
        filetypes = [("Zipped Album files", allowed_extensions),
                     ("All files", "*.*")]
        filename = filedialog.askopenfilename(initialdir=initialdir,
                                              filetypes=filetypes)
        if filename:
            self.load_album(filename, exact=exact)
            self.parent.focus_force()

    def _create_album(self, *args, **kwargs):
        if self.loaded_album is not None:
            initialdir = os.path.split(self.loaded_album.filename)[0]
        else:
            initialdir = os.getcwd()
        directory = filedialog.askdirectory(initialdir=initialdir)
        if directory:
            try:
                self.make_album(directory)
            except AssertionError:
                print("Not a Zipped Album")
            except:
                print("Unknown error")

    def create_menu(self):
        self.menubar = tk.Menu(self.parent)
        if platform.system() == "Darwin":
            modifier = "Command"
            self.apple_menu = tk.Menu(self.menubar, name="apple")
            self.menubar.add_cascade(menu=self.apple_menu, label="Python")
            self.apple_menu.add_command(
                label="About ZAP",
                command=lambda: HelpDialogue(self.master),
                accelerator="F1")
            view_menu_label = "View "  # hack to fix automatic MacOS View menu
        else:
            modifier = "Control"
            view_menu_label = "View"
        self.file_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(menu=self.file_menu, label="File")

        self.file_menu.add_command(label="Open...",
                                   command=self._open_album,
                                   accelerator=f"{modifier}-O")
        self.file_menu.add_command(label="Open exact...",
                                   command=lambda: self._open_album(exact=True))
        self.file_menu.add_command(label="Create...",
                                   command=self._create_album)
        self.options_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(menu=self.options_menu, label="Options")
        self.options_menu.add_checkbutton(label="Repeat",
                                          variable=self.repeat_album)
        self.view_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(menu=self.view_menu, label=view_menu_label)
        self.view_presets_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(menu=self.view_presets_menu, label="Preset")
        self.view_presets_menu.add_command(
            label="Minimal",
            command=lambda: self.set_view_preset("minimal"),
            accelerator=f"{modifier}-1")
        self.view_presets_menu.add_command(
            label="Compact",
            command=lambda: self.set_view_preset("compact"),
            accelerator=f"{modifier}-2")
        self.view_presets_menu.add_command(
            label="Small",
            command=lambda: self.set_view_preset("small"),
            accelerator=f"{modifier}-3")
        self.view_presets_menu.add_command(
            label="Default",
            command=lambda: self.set_view_preset("default"),
            accelerator=f"{modifier}-4")
        self.view_presets_menu.add_command(
            label="Large",
            command=lambda: self.set_view_preset("large"),
            accelerator=f"{modifier}-5")
        self.view_menu.add_command(label="Fit to slides",
                                   command=self.fit_to_slides,
                                   accelerator=f"{modifier}-0")
        self.view_menu.add_checkbutton(
            label="Always on top",
            command=self.toggle_always_on_top)
        self.view_menu.add_checkbutton(label="Fullscreen",
                                       command=self.toggle_fullscreen,
                                       accelerator="F11")
        if platform.system() != "Darwin":
            self.file_menu.add_command(label="Quit",
                                       command=self.quit,
                                       accelerator=f"{modifier}-Q")
            self.help_menu = tk.Menu(self.menubar, tearoff=False)
            self.menubar.add_cascade(menu=self.help_menu, label="Help")
            self.help_menu.add_command(
                label="About",
                command=lambda: HelpDialogue(self.master),
                accelerator="F1")

        self.parent["menu"] = self.menubar

    def change_menu_state(self, state):
        self.menubar.entryconfig("File", state=state)
        self.menubar.entryconfig("Options", state=state)
        if platform.system() == "Darwin":
            self.menubar.entryconfig("Python", state=state)
            self.menubar.entryconfig("View ", state=state)
        else:
            self.menubar.entryconfig("View", state=state)
            self.menubar.entryconfig("Help", state=state)

    def create_widgets(self):
        """Contains all widgets in main application."""

        #self.frame_left = tk.Frame(self)
        #self.frame_left.grid(column=0, row=0, sticky="n")
        #self.frame_left.columnconfigure(0, weight=1)
        #self.frame_left.rowconfigure(1, weight=1)
        self.canvas = ResizingCanvas(self, width=HEIGHT, height=HEIGHT,
                                     bg=COLOUR, borderwidth=0,
                                     highlightthickness=0)
        im = Image.open(os.path.abspath(os.path.join(
            os.path.split(__file__)[0], "no_album.png")))
        im = im.resize((HEIGHT, HEIGHT), Image.LANCZOS)
        self.canvas.image = ImageTk.PhotoImage(im)
        im.close()
        self.canvas_image = self.canvas.create_image(self.canvas.width/2,
                                                     self.canvas.height/2,
                                                     image=self.canvas.image,
                                                     anchor="center")
        self.canvas.grid(column=0, row=0, sticky="nsew")
        self.canvas_left_bg = self.canvas.create_frame(50*SCALING, HEIGHT/2,
                                                       20*SCALING, fill="",
                                                       width=0)
        self.canvas_right_bg = self.canvas.create_frame(HEIGHT-50*SCALING,
                                                        HEIGHT/2,
                                                        20*SCALING, fill="",
                                                        width=0)
        self.canvas_left_fg = self.canvas.create_polygon([52*SCALING,
                                                          HEIGHT/2-10*SCALING,
                                                          42*SCALING,
                                                          HEIGHT/2,
                                                          52*SCALING,
                                                          HEIGHT/2+10*SCALING,
                                                          58*SCALING,
                                                          HEIGHT/2+10*SCALING,
                                                          48*SCALING,
                                                          HEIGHT/2,
                                                          58*SCALING,
                                                          HEIGHT/2-10*SCALING],
                                                         fill='black')
        #self.canvas_left_fg = self.canvas.create_text(50, HEIGHT/2,
                                                      #anchor="center")
        self.canvas_right_fg = self.canvas.create_polygon([HEIGHT-52*SCALING,
                                                           HEIGHT/2-10*SCALING,
                                                           HEIGHT-42*SCALING,
                                                           HEIGHT/2,
                                                           HEIGHT-52*SCALING,
                                                           HEIGHT/2+10*SCALING,
                                                           HEIGHT-58*SCALING,
                                                           HEIGHT/2+10*SCALING,
                                                           HEIGHT-48*SCALING,
                                                           HEIGHT/2,
                                                           HEIGHT-58*SCALING,
                                                           HEIGHT/2-10*SCALING],
                                                          fill='black')
        #self.canvas_right_fg = self.canvas.create_text(HEIGHT-50, HEIGHT/2,
                                                       #anchor="center")
        #self.canvas.itemconfig(self.canvas_left_fg, text="❮", fill="",
        #                       font=(FONTNAME, FONTSIZE+10))
        #self.canvas.itemconfig(self.canvas_right_fg, text="❯", fill="",
                               #font=(FONTNAME, FONTSIZE+10))
        self.canvas_arrow_right = False
        self.canvas_arrow_left = False
        self.canvas.addtag_all("all")
        #self.frame_left.bind("<Configure>", self.canvas.on_resize)

        frame_right = ttk.Frame(self, width=WIDTH-HEIGHT)
        frame_right.grid(column=1, row=0, sticky="nesw")
        frame_right.columnconfigure(0, minsize=WIDTH-HEIGHT, weight=1)
        frame_right.rowconfigure(1, weight=1)
        frame_up = ttk.Frame(frame_right)
        frame_up.grid(column=0, row=0, sticky="nesw")
        frame_up.columnconfigure(0, weight=1)
        frame_up.grid_configure(padx=PADDING, pady=PADDING)
        self.title = ttk.Label(frame_up, text="", anchor="center",
                               font=(FONTNAME, FONTSIZE+8, "bold"),
                               wraplength=WIDTH-HEIGHT-2*PADDING)
        self.title.grid(column=0, row=0, sticky="ew")
        self.artist = ttk.Label(frame_up, text="No Album", anchor="center",
                                font=(FONTNAME, FONTSIZE+4, "italic"),
                                wraplength=WIDTH-HEIGHT-2*PADDING)
        self.artist.grid(column=0, row=1, sticky="ew")
        self.info = ttk.Label(frame_up, text="", anchor="center",
                              font=(FONTNAME, FONTSIZE-2))
        self.info.grid(column=0, row=3, sticky="ew", pady=(PADDING/2, 0))

        self.style.configure("Treeview.Heading", font=(FONTNAME, FONTSIZE))
        self.style.configure("Treeview", font=(FONTNAME, FONTSIZE))
        if SCALING > 1:
            self.style.configure("Treeview", rowheight=int(13 * (SCALING * 1.6)))

        tree_frame = ttk.Frame(frame_right, width=WIDTH-HEIGHT)
        tree_frame.grid(column=0, row=1, sticky="nesw")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree_frame = tree_frame
        self.style.configure('Treeview', relief="flat", borderwidth=1 * SCALING)
        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree.tag_configure('normal', font=(FONTNAME, FONTSIZE))
        self.tree.tag_configure('bold', font=(FONTNAME, FONTSIZE, "bold"))
        self.tree.tag_configure('even', background="#ffffff")
        rgb = [x / 65535 for x in self.winfo_rgb(self.style.lookup(
            'TFrame', 'background'))]
        shaded_colour = get_shaded_colour(rgb, 0.97)
        self.tree.tag_configure('odd', background=shaded_colour)
        self.tree.grid(column=0, row=0, sticky="nesw")
        self.tree["columns"] = ("#", "Title", "Length")
        bold_font = tkfont.Font(family=FONTNAME, size=FONTSIZE, weight="bold")
        self.tree.column('#0', width=0, stretch=False)
        self.tree.column('#', width=0, anchor="e", stretch=False)
        self.tree.column('Title', width=0, anchor="w", stretch=True)
        self.tree.column('Length', width=0, anchor="e", stretch=False)
        self.tree_vscrollbar = AutoScrollbar(tree_frame, orient='vertical',
                                             command=self.tree.yview)
        self.tree_vscrollbar.grid(row=0, column=1, sticky='nsew')
        self.tree.configure(yscrollcommand=self.tree_vscrollbar.set)

        self.track_tooltip = TrackTooltip(self.tree)

        frame_bottom = ttk.Frame(frame_right)
        frame_bottom.grid(column=0, row=2, sticky="nesw")
        frame_bottom.columnconfigure(0, minsize=int(50 * SCALING))
        frame_bottom.columnconfigure(1, weight=1)
        frame_bottom.columnconfigure(2, minsize=int(50 * SCALING))
        frame_bottom.grid_configure(padx=PADDING, pady=PADDING)

        self.playpause_button = ttk.Button(frame_bottom, text="▶", width=1,
                                           command=self.playpause,
                                           takefocus=0, state="disabled")
        self.playpause_button.grid(column=0, row=0, sticky="nesw")

        slider_frame = ttk.Frame(frame_bottom, height=int(10 * SCALING))
        slider_frame.grid(column=1, row=0, sticky="ew", padx=PADDING/2)
        self.style.configure("TProgressbar", period = 0, maxphase =0)
        self.playhead_slider = ttk.Progressbar(slider_frame,
                                               orient="horizontal",
                                               mode='determinate', length=100,
                                               maximum=100, value=0)
        self.playhead_slider.place(relheight=1.0, relwidth=1.0)
        self.playpause_label = ttk.Label(frame_bottom, text="Paused",
                                         anchor="center",
                                         font=(FONTNAME, FONTSIZE-4, "bold"),
                                         state="disabled")
        self.playpause_label.grid(column=0, row=1, sticky="ns")
        self.playhead_label = ttk.Label(frame_bottom, anchor="center",
                                        font=(FONTNAME, FONTSIZE, "bold"))
        self.playhead_label.grid(column=1, row=1, sticky="ns")
        self.playhead = None

        slider_frame = ttk.Frame(frame_bottom, height=int(10 * SCALING))
        slider_frame.grid(column=2, row=0, sticky="ew", padx=PADDING/2)
        self.volume_slider = ttk.Progressbar(slider_frame,
                                             orient="horizontal",
                                             mode='determinate',
                                             length=int(50 * SCALING),
                                             maximum=100, value=100)
        self.volume_slider.place(relheight=1.0, relwidth=1.0)
        self.volume_label = ttk.Label(frame_bottom, anchor="center",
                                      font=(FONTNAME, FONTSIZE-4, "bold"))
        self.volume = 100
        self.volume_label.grid(column=2, row=1, sticky="ns")

        self.trackinfo = ttk.Label(frame_bottom, text="", anchor="center",
                                   font=(FONTNAME, FONTSIZE-2))
        self.trackinfo.grid(column=1, row=2, pady=(PADDING/2, 0))


        for child in self.winfo_children():
            child.grid_configure(padx=0, pady=0)

    def create_bindings(self):

        self.parent.bind("<Configure>", self.schedule_resize)  #self.truncate_titles)

        # Keyboard (global)
        if platform.system() == "Darwin":
            modifier = "Command"
        else:
            modifier = "Control"
        self.parent.bind(f"<{modifier}-o>", self._open_album)
        self.parent.bind(f"<{modifier}-Key-1>",
                         lambda e: self.set_view_preset("minimal"))
        self.parent.bind(f"<{modifier}-Key-2>",
                         lambda e: self.set_view_preset("compact"))
        self.parent.bind(f"<{modifier}-Key-3>",
                         lambda e: self.set_view_preset("small"))
        self.parent.bind(f"<{modifier}-Key-4>",
                         lambda e: self.set_view_preset("default"))
        self.parent.bind(f"<{modifier}-Key-5>",
                         lambda e: self.set_view_preset("large"))
        self.parent.bind(f"<{modifier}-Key-0>", self.fit_to_slides)
        if platform.system() != "Darwin":
            self.parent.bind("<F11>", lambda e: self.toggle_fullscreen())
            self.parent.bind("<F1>", lambda e: HelpDialogue(self.master))
        self.parent.bind(f"<{modifier}-q>", lambda e: self.quit())

        self._last_increment_track = self.now()
        def increment_track(step):
            selected_track_id = self.selected_track_id + step
            if 0 <= selected_track_id < len(self.loaded_album.tracklist):
                if str(self.playpause_button["state"]) == "disabled":
                    return
                play_next = False
                if self.playing_track_id is not None:
                    if self.now() - self._last_increment_track < 0.5:
                        return
                    self._last_increment_track = self.now()
                    self.pause()
                    play_next = True
                selected_track_id = self.selected_track_id + step
                self.tree.selection_set([str(selected_track_id)])
                self.tree.focus(str(selected_track_id))
                self.tree.see(str(selected_track_id))
                self.selected_track_id = selected_track_id
                self.load_track()
                #self.parent.update()
                self.player.clear_on_queue = True
                self.player.seek(0.0)
                if play_next:
                    self.play()

        self.parent.bind("<Down>", lambda e: increment_track(1))
        self.parent.bind("j", lambda e: increment_track(1))
        self.parent.bind("<Up>", lambda e: increment_track(-1))
        self.parent.bind("k", lambda e: increment_track(-1))

        def goto_first_track(e):
            if self.selected_track_id not in (None, 0):
                increment_track(-self.selected_track_id)

        self._first_g_key_pressed = False
        self._first_g_key_time = self.now()

        def goto_first_track_vim(e):
            if self.selected_track_id not in (None, 0):
                if self._first_g_key_pressed:
                    if self.now() - self._first_g_key_time < 1:
                        increment_track(-self.selected_track_id)
                        self._first_g_key_pressed = False
                else:
                    self._first_g_key_pressed = True
                self._first_g_key_time = self.now()

        self.parent.bind("<Home>", goto_first_track)
        self.parent.bind("<g>", goto_first_track_vim)

        def goto_last_track(e):
            length = len(self.loaded_album.tracklist) - 1
            if self.selected_track_id not in (None, length):
                increment_track(length - self.selected_track_id)

        self.parent.bind("<End>", goto_last_track)
        self.parent.bind("<G>", goto_last_track)

        def increment_playhead(step):
            if self.loaded_album is not None:
                if str(self.playpause_button["state"]) == "disabled":
                    return
                track = self.loaded_album.tracklist[self.selected_track_id]
                new_playhead = self.playhead + step
                pos = track["streaminfo"]["duration"] / 100 * new_playhead
                self.playhead = new_playhead
                self.player.seek(pos)

        self.parent.bind(f"<Right>", lambda e: increment_playhead(1))
        self.parent.bind("l", lambda e: increment_playhead(1))
        self.parent.bind("<Left>", lambda e: increment_playhead(-1))
        self.parent.bind("h", lambda e: increment_playhead(-1))

        def seek_to_beginning(e):
            if self.loaded_album is not None:
                if str(self.playpause_button["state"]) == "disabled":
                    return
                self.playhead = 0
                self.player.seek(0.0)

        self.parent.bind("0", seek_to_beginning)
        self.parent.bind("<w>", seek_to_beginning)

        def increment_volume(step):
            self.volume += step

        self.parent.bind(f"<Shift-Up>", lambda e: increment_volume(1))
        self.parent.bind(f"<K>", lambda e: increment_volume(1))
        self.parent.bind(f"<Shift-Down>", lambda e: increment_volume(-1))
        self.parent.bind(f"<J>", lambda e: increment_volume(-1))

        def playpause():
            if hasattr(self, "player"):
                if str(self.playpause_button["state"]) == "disabled":
                    return
                if self.now() - self._last_increment_track < 0.5:
                        return
                playing_id = self.playing_track_id
                self.playpause()
                if playing_id is not None:
                    if self.selected_track_id != playing_id:
                        self.playpause()

        self.parent.bind("<Return>", lambda e: playpause())
        self.parent.bind("<space>", lambda e: playpause())

        def switch_image(step):
            if self.current_image is not None:
                new_image = self.current_image + step
                if 0 <= new_image < self.loaded_album.nr_of_slides:
                    self.show_image(new_image)

        self.parent.bind(f"<Shift-Right>", lambda e: switch_image(1))
        self.parent.bind(f"<L>", lambda e: switch_image(1))
        self.parent.bind(f"<Shift-Left>", lambda e: switch_image(-1))
        self.parent.bind(f"<H>", lambda e: switch_image(-1))

        def switch_to_first_image(e):
            if self.current_image not in (None, 0):
                switch_image(-self.current_image)

        self.parent.bind("<parenright>", switch_to_first_image)
        self.parent.bind("<W>", switch_to_first_image)

        # Mouse (specific widgets)
        self.canvas.bind("<Enter>", lambda e: self.add_arrows())
        self.canvas.bind("<Leave>", lambda e: self.remove_arrows())

        def clicked_canvas_item(e):
            clicked = e.widget.find_closest(e.x, e.y)[0]
            if clicked in (self.canvas_right_bg, self.canvas_right_fg):
                switch_image(1)
            elif clicked in (self.canvas_left_bg, self.canvas_left_fg):
                switch_image(-1)

        self.canvas.bind("<Button-1>", clicked_canvas_item)

        def set_playhead_from_mouseclick(e):
            if self.loaded_album is not None:
                if str(self.playpause_button["state"]) == "disabled":
                    return
                slider = e.widget
                new_playhead = e.x / slider.winfo_width() * slider["maximum"]
                track = self.loaded_album.tracklist[self.selected_track_id]
                pos = track["streaminfo"]["duration"] / 100 * new_playhead
                self.playhead = new_playhead
                self.player.seek(pos)

        self.playhead_slider.bind("<ButtonPress-1>",
                                  set_playhead_from_mouseclick)
        self.playhead_slider.bind("<B1-Motion>", set_playhead_from_mouseclick)

        def set_volume_from_mouseclick(e):
            slider = e.widget
            self.volume = e.x / slider.winfo_width() * slider["maximum"]

        self.volume_slider.bind("<Button-1>", set_volume_from_mouseclick)
        self.volume_slider.bind("<B1-Motion>", set_volume_from_mouseclick)

        def clicked_treeitem(e):
            if str(self.playpause_button["state"]) == "disabled":
                return
            item_id = self.tree.identify('item', e.x, e.y)
            if item_id == "":
                return
            elif item_id == str(self.selected_track_id):
                self.playpause()
            else:
                play = False
                if self.playing_track_id is not None:
                    self.pause()
                    play = True
                selected_track_id = int(item_id)
                self.tree.selection_set([str(selected_track_id)])
                self.tree.focus(str(selected_track_id))
                self.tree.see(str(selected_track_id))
                self.selected_track_id = selected_track_id
                self.load_track()
                self.player.clear_on_queue = True
                self.player.seek(0.0)
                if play:
                    self.play()

        self.tree.bind("<Button-1>", clicked_treeitem)

    def add_arrows(self):
        if self.canvas_arrow_right:
            self.canvas.itemconfig(self.canvas_right_bg,
                                   fill="white",
                                   width=0)
            self.canvas.itemconfig(self.canvas_right_fg, fill="black")
        if self.canvas_arrow_left:
            self.canvas.itemconfig(self.canvas_left_bg,
                                   fill="white",
                                   width=0)
            self.canvas.itemconfig(self.canvas_left_fg, fill="black")
        self.arrows_visible = True

    def remove_arrows(self):
        self.canvas.itemconfig(self.canvas_right_bg, fill="", width=0)
        self.canvas.itemconfig(self.canvas_right_fg, fill="")
        self.canvas.itemconfig(self.canvas_left_bg, fill="", width=0)
        self.canvas.itemconfig(self.canvas_left_fg, fill="")
        self.arrows_visible = False

    def wait_cover_image(self, *args):
        while True:
            if self.loaded_album.get_slide(0) is not None:
                self.show_image(0)
                break

    def show_image(self, nr=0):
        try:
            if nr is None:
                nr = -1
            if nr == -1:
                im = Image.open(os.path.abspath(os.path.join(
            os.path.split(__file__)[0], "no_album.png")))
            else:
                im = Image.open(self.loaded_album.get_slide(nr))

            if im.width != im.height:
                larger = im.width if im.width > im.height else im.height
                bg = Image.new('RGBA', (larger, larger), (0, 0, 0, 255))
                offset = (int(round(((larger - im.width) / 2), 0)),
                          int(round(((larger - im.height) / 2),0)))
                bg.paste(im, offset)
                im = bg

            dim = min(self.canvas.width, self.canvas.height)
            im = im.resize((dim, dim), Image.LANCZOS)
            self.canvas.image = ImageTk.PhotoImage(im)
            im.close()
            try:
                self.canvas.delete(self.canvas_image)
            except:
                pass
            self.canvas_image = self.canvas.create_image(
                self.canvas.width // 2, self.canvas.height // 2,
                image=self.canvas.image, anchor="center")
            self.canvas.tag_lower(self.canvas_image)
            if nr == -1:
                self.current_image = None
            else:
                self.current_image = nr
            if nr < self.loaded_album.nr_of_slides - 1:
                self.canvas_arrow_right = True
            else:
                self.canvas_arrow_right = False
            if nr > 0:
                self.canvas_arrow_left = True
            else:
                self.canvas_arrow_left = False
            if self.arrows_visible:
                self.remove_arrows()
                self.add_arrows()
        except:
            pass

    def hide_image(self):
        try:
            self.canvas.delete(self.canvas_image)
            self.canvas_image = None
        except:
            pass
        self.current_image = None
        self.canvas_arrow_right = False
        self.canvas_arrow_left = False

    def load_album(self, path, exact=False):
        # Clear current state
        self.parent.title("ZAP")
        self.hide_image()
        self.show_image(-1)
        self.loaded_album = None
        if self.playing_track_id is not None:
            self.pause()
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.remove_arrows()
        self.title["text"] = ""
        self.artist["text"] = "Opening Album..."
        self.info["text"] = ""
        self.tree_frame.grid_remove()
        self.tree_frame.grid()
        self.parent.update()

        # Load new album
        try:
            self.loaded_album = ZippedAlbum(path, exact=exact)
        except:
            self.artist["text"] = "No Album"
            file = os.path.split(path)[-1]
            messagebox.showerror(
                title="Error opening album",
                message=f'"{file}" does not seem to be a valid Zipped Album!')
            return

        self.loaded_album.prepare_booklet_pages(self.wait_cover_image)
        self.show_image()
        self.title["text"] = self.loaded_album.title
        self.artist["text"] = self.loaded_album.artist
        year = self.loaded_album.year
        n_tracks = len(self.loaded_album.tracklist)
        playtime = self.loaded_album.playtime
        self.info["text"] = f"{year} | {n_tracks} tracks | {playtime}"

        normal_font = tkfont.Font(family=FONTNAME, size=FONTSIZE)
        bold_font = tkfont.Font(family=FONTNAME, size=FONTSIZE, weight="bold")
        self.title_widths = [normal_font.measure(s["display"][1]) for s in \
                             self.loaded_album.tracklist]
        self.title_widths_bold = [bold_font.measure(s["display"][1]) for s in \
                                  self.loaded_album.tracklist]
        c0_len = sorted([x["display"][0] for x in self.loaded_album.tracklist],
                        key=lambda x: len(x))[-1]
        c0_width = bold_font.measure(c0_len) + CELLPADDING
        self.tree.column("#", width=c0_width)
        c2_len = sorted([x["display"][2] for x in self.loaded_album.tracklist],
                        key=lambda x: len(x))[-1]
        c2_width = bold_font.measure(c2_len) + CELLPADDING
        self.tree.column('Length', width=c2_width)
        # Hack: For some reason the treeview colums do not stretch correctly
        # initially, so hardcode all column sizes
        if self.fullscreen:
            size = self.parent.winfo_geometry().split("+")[0]
            width = int(size.split("x")[0])
            height = int(size.split("x")[1])
        else:
            width = WIDTH
            height = HEIGHT
        c1_width = width - height - 2 - c0_width - c2_width  # 2=2x1 frame borders
        self.tree.column('Title', width=c1_width)
        for c, track in enumerate(self.loaded_album.tracklist):
            if c % 2 == 1:
                tags = ("odd")
            else:
                tags = ("even")
            self.tree.insert(parent='', index=c, iid=c, text='', tags=tags,
                             values=track["display"])
        self.tree.selection_set(["0"])
        self.tree.focus("0")
        self.tree.see("0")
        self.selected_track_id = 0
        self.truncate_titles()

        print(f"Loaded album: {path}")

        if len(set([type(x) for x in self.loaded_album.tracklist])) == 1:
            self.player = GaplessAudioPlayer()
        else:
            self.player = GaplessAudioPlayer()  #AudioPlayer()

        def next_gapless():
            if self.selected_track_id + 1 < len(self.loaded_album.tracklist):
                self.playpause_button["state"] = "disabled"
                track = self.loaded_album.tracklist[self.selected_track_id]
                dur = track["streaminfo"]["duration"]
                tickspeed = UPDATE_INTERVALL / 1000
                pos = self.playhead / 100 * dur + tickspeed
                start = self.now()
                buffer_time = self.player.buffer_time
                # Update GUI after running out of audio data
                while True:
                    current_time = self.now()
                    max_time = min(dur - (pos - tickspeed), 2 * buffer_time)
                    if current_time - start >= max_time:
                        break
                    self.playhead = 100 / dur * (pos + self.now() - start)
                    self.parent.update()
                    sleep_time = tickspeed - (self.now() - current_time)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                self.playpause_button["state"] = "normal"
                tags = self.tree.item(str(self.selected_track_id), "tags")
                tags = [x for x in tags if x != "bold"]
                tags.append("normal")
                self.tree.item(str(self.selected_track_id), tags=tags)
                track_id = self.selected_track_id + 1
                tags = self.tree.item(str(track_id), "tags")
                tags = [x for x in tags if x != "normal"]
                tags.append("bold")
                self.tree.selection_set([str(track_id)])
                self.tree.focus(str(track_id))
                self.tree.see(str(track_id))
                self.tree.item(str(track_id), tags=tags)
                try:
                    self.player.queue(self.loaded_album.get_audio(track_id + 1))
                except:
                    pass
                self.selected_track_id = track_id
                self.playing_track_id = track_id
                self.load_track()
                self.set_title()

        def next():
            self.playpause_button["state"] = "disabled"
            track = self.loaded_album.tracklist[self.selected_track_id]
            dur = track["streaminfo"]["duration"]
            tickspeed = UPDATE_INTERVALL / 1000
            pos = self.playhead / 100 * dur + tickspeed
            start = self.now()
            buffer_time = self.player.buffer_time
            # Update playhead after running out of audio data
            while True:
                current_time = self.now()
                max_time = min(dur - (pos - tickspeed), 2 * buffer_time)
                if current_time - start >= max_time:
                    break
                self.playhead = 100 / dur * (pos + self.now() - start)
                self.parent.update()
                sleep_time = tickspeed - (self.now() - current_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            self.playpause_button["state"] = "normal"
            if self.selected_track_id + 1 < len(self.loaded_album.tracklist):
                tags = self.tree.item(str(self.selected_track_id), "tags")
                tags = [x for x in tags if x != "bold"]
                tags.append("normal")
                self.tree.item(str(self.selected_track_id), tags=tags)
                track_id = self.selected_track_id + 1
                self.player.pause()
                self.player.clear_on_queue = True
                self.player.queue(self.loaded_album.get_audio(track_id))
                self.player.seek(0.0)
                self.player.play()
                tags = self.tree.item(str(track_id), "tags")
                tags = [x for x in tags if x != "normal"]
                tags.append("bold")
                self.tree.selection_set([str(track_id)])
                self.tree.focus(str(track_id))
                self.tree.see(str(track_id))
                self.tree.item(str(track_id), tags=tags)
                self.selected_track_id = track_id
                self.playing_track_id = track_id
                self.load_track()
                self.set_title()
            else:
                if self.playing_track_id is not None:
                    self.pause()
                self.tree.selection_set(["0"])
                self.tree.focus("0")
                self.tree.see("0")
                self.selected_track_id = 0
                self.load_track()
                self.set_title()
                self.player.clear()
                self.player.clear_on_queue = True
                self.player.seek(0.0)
                if self.repeat_album.get():
                    self.play()

        self.player.eos_callback = next
        self.player.eos_gapless_callback = next_gapless

        self.load_track()
        self.track_tooltip.album = self.loaded_album

        self.truncate_titles()
        self.set_title()
        self.create_menu()

    def make_album(self, path, exact=False):
        # Clear current state
        self.parent.title("ZAP")
        self.hide_image()
        self.show_image(-1)
        self.loaded_album = None
        if self.playing_track_id is not None:
            self.pause()
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.remove_arrows()
        self.title["text"] = ""
        self.artist["text"] = "Creating Album..."
        self.info["text"] = ""
        self.parent.update()

        # Make new album
        filename = None
        try:
            filename = create_zipped_album(path)
        except:
            self.artist["text"] = "No Album"
            dir_ = os.path.split(path)[-1]
            messagebox.showerror(
                title="Error creating album",
                message=f'"{dir_}" does not seem to be in a format to create '
                'a Zipped Album from!')
            return
        if filename is not None:
            self.load_album(filename, exact=exact)

    def truncate_titles(self, event=None):
        if self.loaded_album is None:
            return
        if event:
            width = event.width
            if width < self.size[0]:
                return
        width = self.size[0]
        if self.fullscreen:
            tree_width = self.size[0] - self.size[1]
        else:
            tree_width = WIDTH - HEIGHT
        col_width = tree_width - \
                    self.tree.column('0')['width'] - \
                    self.tree.column('2')['width'] - CELLPADDING
        tracks = [x["display"] for x in self.loaded_album.tracklist]
        normal_font = tkfont.Font(family=FONTNAME, size=FONTSIZE)
        bold_font = tkfont.Font(family=FONTNAME, size=FONTSIZE, weight="bold")
        for c, track in enumerate(tracks):
            track = track[:]
            text_width = self.title_widths[c]
            text_width_bold = self.title_widths_bold[c]
            previous_long_text = ''
            new_long_text = ''
            if c == self.playing_track_id and text_width_bold > col_width:
                truncate = True
            elif  c != self.playing_track_id and text_width > col_width:
                truncate = True
            else:
                truncate = False
            if truncate:
                for char in track[1]:
                    new_long_text = f'{new_long_text}{char}'
                    if c == self.playing_track_id:
                        new_width = bold_font.measure(f'{new_long_text}...')
                    else:
                        new_width = normal_font.measure(f'{new_long_text}...')
                    if new_width < col_width:
                        previous_long_text = new_long_text
                    else:
                        track[1] = f'{previous_long_text}...'
                        break
            self.tree.item(c, values=track)

    def load_track(self):
        track = self.loaded_album.tracklist[self.selected_track_id]
        self.playhead_label["text"] = "000:00:00"[-len(track["display"][2]):]
        self.playhead_slider["value"] = 0
        self.playpause_button["state"] = "normal"
        self.playpause_label["state"] = "normal"
        try:
            codec = type(track).__name__
            codec_str = f"{codec} • "
        except:
            codec_str = ""
        try:
            bitrate = int(round(track["streaminfo"]["bitrate"] / 1000))
            bitrate_str = f"{bitrate} kbps • "
        except:
            bitrate_str = ""
        try:
            samplerate = track["streaminfo"]["sample_rate"]
            samplerate_str = f"{samplerate} Hz • "
        except:
            samplerate_str = ""
        try:
            bitdepth = track["streaminfo"]["bit_depth"]
            if self.player.audio_driver == "OpenALDriver" and bitdepth > 16:
                bitdepth_str = f"{bitdepth}→16 bit • "
            else:
                bitdepth_str = f"{bitdepth} bit • "
        except:
            bitdepth_str = ""
        try:
            channels = track["streaminfo"]["channels"]
            if channels == 1:
                channels = "mono"
            elif channels == 2:
                channels = "stereo"
            elif channels > 2:
                channels = f"{channels}ch→stereo"
        except:
            channels = ""
        self.trackinfo["text"] = \
            f"{codec_str}{bitrate_str}{samplerate_str}{bitdepth_str}{channels}"

    def play(self):
        preload_track = False
        tags = self.tree.item(str(self.selected_track_id), "tags")
        tags = [x for x in tags if x != "normal"]
        tags.append("bold")
        self.tree.item(str(self.selected_track_id), tags=tags)
        self.playpause_button["text"] = "❚❚"
        self.playpause_label["text"] = "Playing"
        self.playing_track_id = self.selected_track_id
        self.set_title()
        self.parent.update()
        if self.player.clear_on_queue:
            self.player.queue(self.loaded_album.get_audio(
                self.selected_track_id))
            track = self.loaded_album.tracklist[self.selected_track_id]
            pos = track["streaminfo"]["duration"] / 100 * self.playhead
            self.player.seek(pos)
            if isinstance(self.player, GaplessAudioPlayer):
                preload_track = True
        self.truncate_titles()
        if preload_track:
            try:
                self.player.queue(self.loaded_album.get_audio(
                    self.selected_track_id + 1))
            except:
                pass
        self.player.play()

    def pause(self):
        self.player.pause()
        tags = self.tree.item(str(self.selected_track_id), "tags")
        tags = [x for x in tags if x != "bold"]
        tags.append("normal")
        self.tree.item(str(self.playing_track_id), tags=tags)
        self.playpause_button["text"] = "▶"
        self.playpause_label["text"] = "Paused"
        self.playing_track_id = None
        self.set_title()
        self.truncate_titles()

    def playpause(self):
        if self.playing_track_id is not None:
            self.pause()
        else:
            self.play()

    def schedule_resize(self, event):
        if not (self.size == [event.width, event.height]):
            if self.resize_after_id:
                self.after_cancel(self.resize_after_id)
            self.resize_after_id = self.after(100, self.resize)

    def resize(self, size=None):
        if size:
            width = size[0]
            height = size[1]
        else:
            size = self.parent.winfo_geometry().split("+")[0]
            width = int(size.split("x")[0])
            height = int(size.split("x")[1])
        self.canvas["width"] = height
        self.canvas["height"] = height
        self.size = [width, height]
        #self.canvas.frame_coords(self.canvas_left_bg, 50, height/2, 20)
        #self.canvas.frame_coords(self.canvas_right_bg, height-50, height/2, 20)
        #self.canvas.coords(self.canvas_left_fg, 50, height/2)
        #self.canvas.coords(self.canvas_right_fg, height-50, height/2)
        #self.size = [width, height]
        if self.loaded_album is None:
            current_image = None
        else:
            current_image = self.current_image
        self.show_image(current_image)

    def set_view_preset(self, preset="default", event=None):
        global HEIGHT
        global WIDTH
        if preset == "minimal":
            width = WIDTH-HEIGHT
            height = 0
        elif preset == "compact":
            width = WIDTH - HEIGHT
            height = WIDTH - HEIGHT
        elif preset == "small":
            width = (WIDTH - HEIGHT) * 2
            height = WIDTH - HEIGHT
        elif preset == "default":
            width = WIDTH
            height = HEIGHT
        elif preset == "large":
            #if platform.system() in ("Windows", "Darwin"):
            #    self.parent.state("zoomed")
            #else:
            #    self.parent.wm_attributes("zoomed", True)
            #self.fit_to_slides()
            #return
            if platform.system() == "Windows":
                self.parent.attributes("-alpha", 0)
                self.parent.state('zoomed')
                self.parent.update()
                max_width  = self.parent.winfo_width()
                max_height = self.parent.winfo_height()
                self.parent.state('normal')
                self.parent.update()
                self.parent.attributes("-alpha", 1)
            else:
                max_width, max_height = self.parent.maxsize()
            if max_width > max_height:
                width = max_height + (WIDTH - HEIGHT)
                height = max_height
            else:
                width = max_width
                height = max_width - (WIDTH - HEIGHT)
        self.parent.geometry(f"{width}x{height}")

    def fit_to_slides(self, event=None):
        if not self.fullscreen:
            width = self.parent.winfo_width() - (WIDTH - HEIGHT)
            height = self.parent.winfo_height()
            if width > height:
                self.parent.geometry(f"{height + (WIDTH - HEIGHT)}x{height}")
            elif width < height:
                self.parent.geometry(f"{width + (WIDTH - HEIGHT)}x{width}")

    def toggle_always_on_top(self, event=None):
        self.parent.attributes('-topmost', not self.always_on_top)
        self.always_on_top = not self.always_on_top

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.columnconfigure(0, weight=int(not self.fullscreen))
        self.columnconfigure(1, weight=int(self.fullscreen))
        #if self.fullscreen:
        #    self.parent.withdraw()
        self.parent.attributes("-fullscreen", self.fullscreen)
        if self.fullscreen:
            self.update()
            self.update()
            #self.parent.deiconify()
            size = self.parent.winfo_geometry().split("+")[0]
            width = int(size.split("x")[0])
            height = int(size.split("x")[1])
            #self.parent.state("normal")
        else:
            width = WIDTH
            height = HEIGHT
        self.size = (width, height)
        self.resize((width, height))
        self.title.configure(wraplength=width-height-2*PADDING)
        self.artist.configure(wraplength=width-height-2*PADDING)
        #self.parent.columnconfigure(0, weight=int(self.fullscreen))
        #self.parent.columnconfigure(1, weight=int(not self.fullscreen))
        #self.parent.rowconfigure(0, weight=int(self.fullscreen))
        #self.parent.geometry(f"{width}x{height}+0+0")
        if self.loaded_album is None:
            current_image = None
        else:
            current_image = self.current_image
        self.show_image(current_image)
        self.truncate_titles()

    def set_title(self):
        title = "ZAP"
        if self.loaded_album is not None:
            album = self.loaded_album.title
            artist = self.loaded_album.artist
            path, file = os.path.split(self.loaded_album.filename)
            path = path.replace(os.path.expanduser('~'), '~')
            prefix = f"{album} • {artist} | {file} ({path}) • "
            title = prefix + title
            if self.playing_track_id is not None:
                tracknumber = self.loaded_album.tracklist[
                    self.playing_track_id]["display"][0]
                tracktitle = self.loaded_album.tracklist[
                    self.playing_track_id]["display"][1]
                prefix = f"{tracknumber} • {tracktitle} | "
                title = prefix + title
        self.parent.title(title)

    def quit(self):
        self.player = None
        del self.player
        self.parent.destroy()

def run():
    if platform.system() == "Windows":
        try:
            import ctypes
            id_ = 'mycompany.myproduct.subproduct.version' # arbitrary
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(id_)
        except:
            pass

    root = tk.Tk()
    dpi = root.winfo_fpixels('1i')
    root.tk.call('tk', 'scaling', SCALING * (dpi / 72.0))
    root.withdraw()
    app = MainApplication(root, padding="0 0 0 0")
    app.set_title()
    if platform.system() == "Windows":
        root.iconbitmap(os.path.abspath(os.path.join(
            os.path.split(__file__)[0], "zipped_album_icon.ico")))
    else:
        root.tk.call('wm', 'iconphoto', root._w,
                     tk.PhotoImage(file=os.path.abspath(os.path.join(
                os.path.split(__file__)[0], "zipped_album_icon.png"))))
    app.pack(side="top", fill="both", expand=True)
    root.geometry(f"{WIDTH}x{HEIGHT}+0+0")
    root.update()
    root.deiconify()
    root.minsize(WIDTH-HEIGHT, 0)
    root.lift()
    root.focus_force()
    root.protocol('WM_DELETE_WINDOW', app.quit)
    root.geometry(f"{WIDTH-1}x{HEIGHT-1}")  # hack for removing empty scrollbar
    root.update_idletasks()
    root.geometry(f"{WIDTH}x{HEIGHT}")

    from .binaries import has_ffmpeg
    if not has_ffmpeg():
        app.change_menu_state("disabled")
        if messagebox.askyesno(title="Download FFmpeg",
                               message="Required FFmpeg libraries could not"
                               " be found on the system!\n\n"
                               "Attempt to download a local copy?"):
            DownloadFFmpegDialogue(app).start()
            app.change_menu_state("normal")

    try:
        global AudioPlayer, GaplessAudioPlayer
        from .player import AudioPlayer, GaplessAudioPlayer
    except RuntimeError as e:
        if "ffmpeg" in repr(e).lower():
            messagebox.showerror(title="FFmpeg error",
                                 message="There was an error loading the "
                                         "required FFmpeg libraries!"
                                         "\n\nThe application will close now.")
            sys.exit()

    try:
        if "--exact" in sys.argv:
            exact = True
        else:
            exact = False
        if "--create" in sys.argv:
            create = True
        else:
            create = False
        if os.path.isdir(sys.argv[-1]):
            if create:
                app.make_album(os.path.abspath(sys.argv[-1]), exact=exact)
            else:
                os.chdir(os.path.abspath(sys.argv[-1]))
        if os.path.splitext(sys.argv[-1])[-1] in (".zlbm", ".zip"):
            if os.path.isfile(sys.argv[-1]):
                app.load_album(os.path.abspath(sys.argv[-1]), exact=exact)
            else:
                messagebox.showerror(
                title="Error opening album",
                message=f'The file "{sys.argv[-1]}" does not exist!')
    except:
        pass

    app.create_bindings()
    root.mainloop()


if __name__ == "__main__":
    run()

