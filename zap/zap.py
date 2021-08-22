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
except ImportError:
    print("Error: Tkinter not found!")
except ModuleNotFoundError:
    print("Error: Python not configured for Tk!")
    sys.exit()

from PIL import ImageTk, Image

from .__meta__ import __author__, __version__
from .album import ZippedAlbum
from .player import AudioPlayer, GaplessAudioPlayer


WIDTH = 1024
HEIGHT = 600
PADDING = 8
CELLPADDING = 8 #8=2x4 cell padding
if platform.system() == "Windows":
    FONTNAME = "Calibri"
    FONTSIZE = 11
elif platform.system() == "Darwin":
    FONTNAME = "Helvetica Neue"
    FONTSIZE = 13
else:
    FONTNAME = "Nimbus Sans L"
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
 │  Play/Pause:                               Return           |      Space  │
 │  Select next track:                        Down             |      j      │
 │  Select previous track:                    Up               |      k      │
 │  Select first track:                       Home             |      gg     │
 │  Seek forward:                             Right            |      l      │
 │  Seek backward:                            Left             |      h      │
 │  Seek to beginning:                        Numpad 0         |      0      │
 │  Show next slide:                          Shift-Right      |      L      │
 │  Show previous slide:                      Shift-Left       |      H      │
 │  Increase volume:                          Shift-Right      |      K      │
 │  Decrease volume:                          Shift-Left       |      J      │
 │                                                                           │
 └───────────────────────────────────────────────────────────────────────────┘
""".format(ver=__version__)

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
            year = "; ".join([str(
                dateutil.parser.parse(x).year) for x in track["tags"]["date"]])
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


class MainApplication(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.style = ttk.Style()
        self.size = [WIDTH, HEIGHT]
        self.create_menu()
        self.create_widgets()
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.fullscreen = False
        self.repeat_album = False
        self.create_bindings()
        self.loaded_album = None
        self.current_image = None
        self.selected_track_id = None
        self.playing_track_id = None

        def update_player():
            intervall = 100
            if hasattr(self, "player") and self.player.is_playing:
                self.player.update()
                track = self.loaded_album.tracklist[self.selected_track_id]
                time = self.player.time
                self.playhead = 100 / track["streaminfo"]["duration"] * time
                if self.player.audio_driver == "PulseAudioDriver":
                    intervall = 10
            self.after(intervall, update_player)

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

    def create_menu(self):
        self.menubar = tk.Menu(self.parent)
        if platform.system() == "Darwin":
            modifier = "Command"
            self.apple_menu = tk.Menu(self.menubar, name="apple")
            self.menubar.add_cascade(menu=self.apple_menu)
            self.apple_menu.add_command(
                label="About ZAP",
                command=lambda: HelpDialogue(self.master),
                accelerator="F1")
        else:
            modifier = "Control"
        self.file_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(menu=self.file_menu, label="File")

        def open_album(e=None):
            allowed_extensions = "*.zip *.zlbm"
            filetypes = [("Zipped Album files", allowed_extensions),
                         ("All files", "*.*")]
            filename = filedialog.askopenfilename(filetypes=filetypes)
            if filename:
                self.load_album(filename)
            self.parent.focus_force()

        self.file_menu.add_command(label="Open",
                                   command=open_album,
                                   accelerator=f"{modifier}-O")
        self.parent.bind(f"<{modifier}-o>", open_album)

        self.options_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(menu=self.options_menu, label="Options")
        self.options_menu.add_checkbutton(label="Repeat",
                                          command=self.toggle_repeat_album)
        self.options_menu.add_checkbutton(label="Fullscreen",
                                          command=self.toggle_fullscreen,
                                          accelerator="F11")
        self.parent.bind("<F11>", lambda e: self.toggle_fullscreen())

        if platform.system() != "Darwin":
            self.file_menu.add_command(label="Quit",
                                       command=self.master.destroy,
                                       accelerator=f"{modifier}-Q")
            self.help_menu = tk.Menu(self.menubar, tearoff=False)
            self.menubar.add_cascade(menu=self.help_menu, label="Help")
            self.help_menu.add_command(
                label="About",
                command=lambda: HelpDialogue(self.master),
                accelerator="F1")

        self.parent.bind("<F1>", lambda e: HelpDialogue(self.master))
        self.parent.bind(f"<{modifier}-q>",
                         lambda e: self.master.destroy())

        self.parent["menu"] = self.menubar

    def create_widgets(self):
        """Contains all widgets in main application."""

        frame_left = tk.Frame(self)
        frame_left.grid(column=0, row=0, sticky="n")
        frame_left.columnconfigure(0, weight=1)
        frame_left.rowconfigure(1, weight=1)
        self.canvas = tk.Canvas(frame_left, width=HEIGHT, height=HEIGHT,
                                bg=COLOUR, borderwidth=0,
                                highlightthickness=0)
        im = Image.open(os.path.abspath(os.path.join(
            os.path.split(__file__)[0], "no_album.png")))
        im = im.resize((HEIGHT, HEIGHT), Image.LANCZOS)
        self.canvas.image = ImageTk.PhotoImage(im)
        im.close()
        self.canvas_image = self.canvas.create_image(
                0, 0, image=self.canvas.image, anchor="nw")
        self.canvas.grid(column=0, row=0)
        self.canvas_left_bg = self.canvas.create_frame(50, HEIGHT/2,
                                                       20, fill="",
                                                       width=0)
        self.canvas_right_bg = self.canvas.create_frame(HEIGHT-50, HEIGHT/2,
                                                        20, fill="",
                                                        width=0)
        self.canvas_left_fg = self.canvas.create_text(50, HEIGHT/2,
                                                      anchor="center")
        self.canvas_right_fg = self.canvas.create_text(HEIGHT-50, HEIGHT/2,
                                                       anchor="center")
        self.canvas.itemconfig(self.canvas_left_fg, text="❮", fill="",
                               font=(FONTNAME, FONTSIZE+10))
        self.canvas.itemconfig(self.canvas_right_fg, text="❯", fill="",
                               font=(FONTNAME, FONTSIZE+10))
        self.canvas_arrow_right = False
        self.canvas_arrow_left = False

        frame_right = ttk.Frame(self)
        frame_right.grid(column=1, row=0, sticky="nesw")
        frame_right.columnconfigure(0, weight=1)
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

        tree_frame = ttk.Frame(frame_right)
        tree_frame.grid(column=0, row=1, sticky="nesw")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.style.configure('Treeview', relief="flat", borderwidth=1)
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
        self.tree.column('#', anchor="e", stretch=False)
        self.tree.column('Title', anchor="w", stretch=True)
        self.tree.column('Length', anchor="e", stretch=False)
        self.tree_vscrollbar = AutoScrollbar(tree_frame, orient='vertical',
                                             command=self.tree.yview)
        self.tree_vscrollbar.grid(row=0, column=1, sticky='nsew')
        self.tree.configure(yscrollcommand=self.tree_vscrollbar.set)

        self.track_tooltip = TrackTooltip(self.tree)

        frame_bottom = ttk.Frame(frame_right)
        frame_bottom.grid(column=0, row=2, sticky="nesw")
        frame_bottom.columnconfigure(0, minsize=50)
        frame_bottom.columnconfigure(1, weight=1)
        frame_bottom.columnconfigure(2, minsize=50)
        frame_bottom.grid_configure(padx=PADDING, pady=PADDING)

        self.playpause_button = ttk.Button(frame_bottom, text="▶", width=1,
                                           command=self.playpause,
                                           takefocus=0, state="disabled")
        self.playpause_button.grid(column=0, row=0, sticky="nesw")

        slider_frame = ttk.Frame(frame_bottom, height=10)
        slider_frame.grid(column=1, row=0, sticky="ew", padx=PADDING/2)
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

        slider_frame = ttk.Frame(frame_bottom, height=10)
        slider_frame.grid(column=2, row=0, sticky="ew", padx=PADDING/2)
        self.volume_slider = ttk.Progressbar(slider_frame,
                                             orient="horizontal",
                                             mode='determinate', length=50,
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

        self.parent.bind("<Configure>", self.truncate_titles)

        # Keyboard (global)
        def increment_track(step):
            selected_track_id = self.selected_track_id + step
            if 0 <= selected_track_id < len(self.loaded_album.tracklist):
                play_next = False
                if self.playing_track_id is not None:
                    self.pause()
                    play_next = True
                selected_track_id = self.selected_track_id + step
                self.tree.selection_set([str(selected_track_id)])
                self.selected_track_id = selected_track_id
                self.load_track()
                self.parent.update()
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

        self.parent.bind("<Home>", goto_first_track)
        self.parent.bind("<g><g>", goto_first_track)

        def increment_playhead(step):
            if self.loaded_album is not None:
                track = self.loaded_album.tracklist[self.selected_track_id]
                new_playhead = self.playhead + step
                pos = track["streaminfo"]["duration"] / 100 * new_playhead
                if pos < track["streaminfo"]["duration"] - 2:
                    self.playhead = new_playhead
                    self.player.seek(pos)

        self.parent.bind(f"<Right>", lambda e: increment_playhead(1))
        self.parent.bind("l", lambda e: increment_playhead(1))
        self.parent.bind("<Left>", lambda e: increment_playhead(-1))
        self.parent.bind("h", lambda e: increment_playhead(-1))

        def seek_to_beginning(e):
            if self.loaded_album is not None:
                self.playhead = 0
                self.player.seek(0.0)

        self.parent.bind("0", seek_to_beginning)

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
                slider = e.widget
                new_playhead = e.x / slider.winfo_width() * slider["maximum"]
                track = self.loaded_album.tracklist[self.selected_track_id]
                pos = track["streaminfo"]["duration"] / 100 * new_playhead
                if pos < track["streaminfo"]["duration"] - 2:
                    self.playhead = new_playhead
                    self.player.seek(pos)

        self.playhead_slider.bind("<ButtonPress-1>", set_playhead_from_mouseclick)
        self.playhead_slider.bind("<B1-Motion>", set_playhead_from_mouseclick)

        def set_volume_from_mouseclick(e):
            slider = e.widget
            self.volume = e.x / slider.winfo_width() * slider["maximum"]

        self.volume_slider.bind("<Button-1>", set_volume_from_mouseclick)
        self.volume_slider.bind("<B1-Motion>", set_volume_from_mouseclick)

        def clicked_treeitem(e):
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
                nr = 0
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

            im = im.resize((self.size[1], self.size[1]), Image.LANCZOS)
            self.canvas.image = ImageTk.PhotoImage(im)
            im.close()
            try:
                self.canvas.delete(self.canvas_image)
            except:
                pass
            self.canvas_image = self.canvas.create_image(
                0, 0, image=self.canvas.image, anchor="nw")
            self.canvas.tag_lower(self.canvas_image)
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

    def load_album(self, path):
        # Clear current state
        self.parent.title("ZAP")
        self.hide_image()
        im = Image.open(os.path.abspath(os.path.join(
            os.path.split(__file__)[0], "no_album.png")))
        im = im.resize((self.size[1], self.size[1]), Image.LANCZOS)
        self.canvas.image = ImageTk.PhotoImage(im)
        im.close()
        self.canvas_image = self.canvas.create_image(
                0, 0, image=self.canvas.image, anchor="nw")
        self.loaded_album = None
        if self.playing_track_id is not None:
            self.playpause()
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.remove_arrows()
        self.title["text"] = ""
        self.artist["text"] = "Opening Album..."
        self.info["text"] = ""
        self.parent.update()

        # Load new album
        try:
            self.loaded_album = ZippedAlbum(path)
        except AssertionError:
            self.artist["text"] = "No Album"
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
        c1_width = self.size[0]-self.size[1]-2-c0_width-c2_width  # 2=2x1 frame borders
        self.tree.column('Title', width=c1_width)
        for c, track in enumerate(self.loaded_album.tracklist):
            if c % 2 == 1:
                tags = ("odd")
            else:
                tags = ("even")
            self.tree.insert(parent='', index=c, iid=c, text='', tags=tags,
                             values=track["display"])
        self.tree.selection_set(["0"])
        self.selected_track_id = 0

        print(f"Loaded album: {path}")

        if len(set([type(x) for x in self.loaded_album.tracklist])) == 1:
            self.player = GaplessAudioPlayer()
        else:
            self.player = AudioPlayer()

        def next_gapless():
            if self.selected_track_id + 1 < len(self.loaded_album.tracklist):
                tags = self.tree.item(str(self.selected_track_id), "tags")
                tags = [x for x in tags if x != "bold"]
                tags.append("normal")
                self.tree.item(str(self.selected_track_id), tags=tags)
                track_id = self.selected_track_id + 1
                tags = self.tree.item(str(track_id), "tags")
                tags = [x for x in tags if x != "normal"]
                tags.append("bold")
                self.tree.selection_set([str(track_id)])
                self.tree.item(str(track_id), tags=tags)
                try:
                    self.player.queue(self.loaded_album.get_audio(track_id + 1))
                except:
                    pass
                self.selected_track_id = track_id
                self.playing_track_id = track_id
                self.load_track()

        def next():
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
                self.tree.item(str(track_id), tags=tags)
                self.selected_track_id = track_id
                self.playing_track_id = track_id
                self.load_track()
            else:
                track = self.loaded_album.tracklist[self.selected_track_id]
                dur = track["streaminfo"]["duration"]
                tickspeed = 0.1
                if self.player.audio_driver == "PulseAudioDriver":
                    tickspeed = 0.01
                pos = self.playhead / 100 * dur + tickspeed
                start = time.time()
                self.playpause_button["state"] = "disabled"
                while time.time() - start < dur - pos:
                    self.playhead = 100 / dur * (pos + time.time() - start)
                    self.parent.update()
                    time.sleep(tickspeed)
                self.playpause_button["state"] = "normal"
                self.pause()
                self.tree.selection_set(["0"])
                self.selected_track_id = 0
                self.load_track()
                self.player.clear()
                self.player.clear_on_queue = True
                self.player.seek(0.0)
                if self.repeat_album:
                    self.play()

        self.player.eos_callback = next
        self.player.eos_gapless_callback = next_gapless

        self.load_track()
        self.track_tooltip.album = self.loaded_album

        self.truncate_titles()
        self.set_title()
        self.create_menu()

    def truncate_titles(self, event=None):
        if self.loaded_album is None:
            return
        if event:
            width = event.width
            if width < self.size[0]:
                return
        else:
            width = self.size[0]
        col_width = width - self.size[1] - \
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

    def toggle_fullscreen(self):
        fullscreen = not self.fullscreen
        if platform.system() == "Windows":
            self.parent.withdraw()
            if fullscreen:
                self.parent.overrideredirect(True)
                self.parent.state("zoomed")
            else:
                self.parent.overrideredirect(False)
                self.parent.state("normal")
            self.parent.deiconify()
        else:
            if fullscreen:
                self.parent.withdraw()
            self.parent.attributes("-fullscreen", fullscreen)
            if fullscreen:
                self.update()
                self.update()
                self.parent.deiconify()
        if fullscreen:
            size = self.parent.winfo_geometry().split("+")[0]
            width = int(size.split("x")[0])
            height = int(size.split("x")[1])
            self.parent.state("normal")
        else:
            width = WIDTH
            height = HEIGHT

        self.canvas["width"] = height
        self.canvas["height"] = height
        self.canvas.frame_coords(self.canvas_left_bg, 50, height/2, 20)
        self.canvas.frame_coords(self.canvas_right_bg, height-50, height/2, 20)
        self.canvas.coords(self.canvas_left_fg, 50, height/2)
        self.canvas.coords(self.canvas_right_fg, height-50, height/2)
        self.size = [width, height]
        if self.loaded_album is None:
            current_image = -1
        else:
            current_image = self.current_image
        self.show_image(current_image)
        self.title.configure(wraplength=width-height-2*PADDING)
        self.artist.configure(wraplength=width-height-2*PADDING)
        self.parent.columnconfigure(0, weight=int(fullscreen))
        self.parent.rowconfigure(0, weight=int(fullscreen))
        self.parent.resizable(fullscreen, fullscreen)
        self.parent.geometry(f"{width}x{height}")
        self.fullscreen = fullscreen

    def toggle_repeat_album(self):
        if self.repeat_album:
            self.repeat_album = False
        else:
            self.repeat_album = True

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


def run():
    if platform.system() == "Windows":
        try:
            import ctypes
            id_ = 'mycompany.myproduct.subproduct.version' # arbitrary
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(id_)
        except:
            pass

    root = tk.Tk()
    root.withdraw()
    root.resizable(False, False)
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
    root.geometry(f"{WIDTH}x{HEIGHT}")
    root.update()
    root.deiconify()
    root.minsize(root.winfo_width(), root.winfo_height())
    root.lift()
    root.focus_force()

    try:
        app.load_album(os.path.abspath(sys.argv[1]))
    except:
        pass

    root.mainloop()


if __name__ == "__main__":
    run()
