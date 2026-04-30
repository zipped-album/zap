import io
import platform

import tkinter as tk
import tkinter.ttk as ttk

from PIL import Image, ImageTk
from PIL import __version__ as pil_version

from .utils import get_hex_colour, FontBase


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

    def create_frame(self, x, y, r, **kwargs):
        return self.create_rectangle(x-r, y-r, x+r, y+r, **kwargs)

    def frame_coords(self, frame_id, x, y, r):
        self.coords(frame_id, x-r, y-r, x+r, y+r)

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


class CanvasProgressbar(tk.Canvas):
    def __init__(self, master, **kwargs):
        # 1. Extract values before Canvas init
        self._maximum = float(kwargs.pop('maximum', 100))
        self._value = float(kwargs.pop('value', 0))

        for key in ('orient', 'mode', 'length', 'period', 'maxphase'):
            kwargs.pop(key, None)

        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('bd', 0)
        kwargs.setdefault('bg', '#222')

        super().__init__(master, **kwargs)

        self.bar = self.create_rectangle(0, 0, 0, 0, fill="#007AFF", outline="")
        self.bind("<Configure>", lambda e: self._update_view())

    def _update_view(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1: return
        fill_w = (self._value / self._maximum) * w if self._maximum > 0 else 0
        self.coords(self.bar, 0, 0, fill_w, h)

    @property
    def value(self): return self._value

    @value.setter
    def value(self, v):
        self._value = float(v)
        self.after_idle(self._update_view)

    def __getitem__(self, key):
        """Intercepts self.playhead_slider['value']"""
        if key == 'value':
            return self._value
        if key == 'maximum':
            return self._maximum
        return super().cget(key)

    def cget(self, key):
        """Some internal calls use .cget() directly."""
        return self.__getitem__(key)

    def __setitem__(self, key, val):
        """Intercepts self.playhead_slider['value'] = x"""
        if key == 'value':
            self.value = val
        elif key == 'maximum':
            self._maximum = float(val)
            self._update_view()
        else:
            super().configure(**{key: val})


class TrackTooltip:
    def __init__(self, treeview, bg_colour, default_fonts, app_always_on_top):
        self.treeview = treeview
        self.default_fonts = default_fonts
        self.bg_colour = bg_colour
        self.app_always_on_top = app_always_on_top
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

    def activate(self):
        self.treeview.bind("<Motion>", self.schedule)
        self.treeview.bind("<Leave>", self.leave)

    def deactivate(self):
        self.leave(None)
        self.treeview.unbind("<Motion>")
        self.treeview.unbind("<Leave>")

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
        #normal_font = tkfont.Font(family=FONTNAME, size=_px(FONTSIZE-2))
        #bold_font = tkfont.Font(family=FONTNAME, size=_px(FONTSIZE-2),
        #                        weight="bold")
        #italic_font = tkfont.Font(family=FONTNAME, size=_px(FONTSIZE-2),
        #                          slant="italic")

        idd = self.treeview.identify_row(event.y)
        if idd == "":
            return
        self.tooltip_window = tk.Toplevel(self.treeview, highlightthickness=1,
                                          bg="white")
        rgb = [x / 65535 for x in self.tooltip_window.winfo_rgb(
            self.style.lookup('TFrame', 'background'))]
        highlight_colour = get_hex_colour(rgb, 0.52)
        self.tooltip_window["highlightbackground"] = highlight_colour

        if platform.system() == "Darwin":
            self.tooltip_window.tk.call("::tk::unsupported::MacWindowStyle",
                                         "style", self.tooltip_window._w,
                                         "help", "noActivates")
        else:
            self.tooltip_window.wm_overrideredirect(1)
        self.tooltip_window.columnconfigure(2, weight=1)
        track = self.album.tracklist[int(idd)]
        tags = track["tags"].keys()
        if track["pictures"] != []:
            im = Image.open(io.BytesIO(track["pictures"][0].data))
        else:
            im = Image.open(self.album.get_slide(0))
        if int(pil_version.split(".")[0]) < 10:
            im = im.resize((100, 100), Image.ANTIALIAS)
        else:
            im = im.resize((100, 100), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(im)
        im.close()
        label = tk.Label(self.tooltip_window, image=self.photo,
                         bg=self.bg_colour,
                         borderwidth=0, highlightthickness=0, padx=0, pady=0)
        label.grid(row=0, column=0, sticky="nw")
        self.style.configure('TFrame',
                             background=self.style.lookup('TFrame',
                                                          'background'))
        self.frame = ttk.Frame(self.tooltip_window)
        self.frame.columnconfigure(0, minsize=200)
        self.frame.grid(row=0, column=1, sticky="nesw")
        try:
            title = "; ".join(track["tags"]["title"])
        except:
            title = "Unknown Title"
        label = ttk.Label(self.frame, text=title, justify=tk.LEFT,
                          font=self.default_fonts.spec(-2, weight="bold"),
                          #font=bold_font,
                          wraplength=self.treeview.winfo_width() - 120)
        label.grid(row=0, column= 0, padx=2, ipadx=0, ipady=0, sticky="nw")
        try:
            artist = "; ".join(track["tags"]["artist"])
        except:
            artist = "Unknown Artist"
        label = ttk.Label(self.frame,
                          text=artist, justify=tk.LEFT,
                          font=self.default_fonts.spec(-2, slant="italic"),
                          #font=italic_font,
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
                          font=self.default_fonts.spec(-2),
                          #font=normal_font,
                          wraplength=self.treeview.winfo_width() - 120)
        label.grid(row=2, column= 0, padx=2, ipadx=0, ipady=0, sticky="nw")

        try:
            x, y, cx, cy = self.treeview.bbox(idd)
        except ValueError:
            return
        x = x + self.treeview.winfo_rootx() + event.x + 15
        rowheight = self.style.lookup("Treeview", "rowheight")
        if rowheight == "":
            rowheight = 20
        y = y + cy + self.treeview.winfo_rooty() - rowheight // 2 - 50
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        self.tooltip_window.update()
        try:
            self.tooltip_window.attributes('-topmost',
                                           self.app_always_on_top.get())
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

