import os
import shutil
import platform
import subprocess

import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog
from tkinter import messagebox

from .__init__ import __version__
from .utils import get_config_folder


class DialogueWindow(tk.Toplevel):
    TITLE = ""
    TRANSIENT = platform.system() != "Darwin"
    UNMANAGED = False
    MODAL = False

    _instances = {}

    def __init__(self, parent):
        self.root = parent.nametowidget(".")
        if self.TRANSIENT:
            tk.Toplevel.__init__(self, parent)
            self.transient(parent)
        else:
            tk.Toplevel.__init__(self, self.root)
            self.transient(self.root)

        # Allow only one instance
        cls = self.__class__
        if cls in DialogueWindow._instances and \
                DialogueWindow._instances[cls].winfo_exists():
            DialogueWindow._instances[cls].lift()
            DialogueWindow._instances[cls].focus_force()
            self.destroy()
            return
        DialogueWindow._instances[cls] = self

        self.parent = parent
        self.withdraw()

        self.title(self.TITLE)
        self.resizable(False, False)

        if self.UNMANAGED:
            self.overrideredirect(True)
        else:
            self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", self.close)

        self.create_widgets()
        self.update_idletasks()
        self.set_geometry()

        self.deiconify()
        self.lift()
        self.focus_set()

        if self.MODAL:
            self.grab_set()
            if platform.system() == "Windows":
                parent.wm_attributes("-disabled", True)

        self.on_show()

    def create_widgets(self):
        pass

    def set_geometry(self):
        # Center window by default
        px, py = self.parent.winfo_rootx(), self.parent.winfo_rooty()
        pw, ph = self.parent.winfo_width(), self.parent.winfo_height()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = px + (pw // 2) - (w // 2)
        y = py + (ph // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def on_show(self):
        pass

    def wait(self):
        if not self.winfo_exists():
            return
        self.wait_window()

    def close(self, event=None):
        cls = self.__class__
        if DialogueWindow._instances.get(cls) == self:
            del DialogueWindow._instances[cls]

        if self.MODAL:
            if platform.system() == "Windows":
                self.parent.wm_attributes("-disabled", False)
            self.grab_release()

        self.destroy()


class AboutDialogue(DialogueWindow):
    TITLE = "About ZAP"

    def create_widgets(self):
        with open(os.path.join(os.path.split(__file__)[0], "ABOUT.txt")) as f:
            about_text = f.read()
        self.text = tk.Text(self, width=79, height=len(about_text.split("\n")))
        self.text.pack(expand=True, fill="both")
        self.text.insert(tk.END, about_text.format(ver=__version__))
        self.text["state"] = "disabled"


class SettingsWindow(DialogueWindow):
    TITLE = "ZAP Settings"

    def create_widgets(self):
        padding = self.parent.padding
        self.frame = ttk.Frame(self)
        self.frame.pack()

        style = ttk.Style()
        style.configure("TLabelframe.Label",
                        font=self.parent.default_fonts.spec(weight="bold"))

        # Audio
        from .player import AudioPlayer
        self.available_audio_systems = AudioPlayer.available_audio_systems
        self.available_sample_formats = AudioPlayer.available_sample_formats

        audio_frame = ttk.LabelFrame(self.frame,
                                     text="Audio",
                                     padding=(padding/2, padding/4*3))
        audio_frame.pack(fill="x", padx=padding, pady=padding)

        ttk.Label(audio_frame, text="Audio System:").grid(
            row=0, column=0, sticky="w",)
        self.audio_system = ttk.Combobox(
            audio_frame,
            values=list(self.available_audio_systems.keys()),
            state="readonly")
        self.audio_system.set(self.parent.audio_system)
        self.audio_system.bind("<<ComboboxSelected>>",
                               self.update_audio_values)
        self.audio_system.grid(row=0, column=1, sticky="ew")
        ttk.Label(audio_frame, text="Channel Mode:").grid(
            row=1, column=0, sticky="w",)
        self.channel_mode = ttk.Combobox(
            audio_frame,
            values=("Automatic", "Mono", "Dual-Mono", "Stereo"),
            state="readonly")
        self.channel_mode.set(self.parent.channel_mode)
        self.channel_mode.bind("<<ComboboxSelected>>",
                               self.update_audio_values)
        self.channel_mode.grid(row=1, column=1, sticky="ew")
        ttk.Label(audio_frame, text="Sample Format:").grid(
            row=2, column=0, sticky="w")
        self.sample_format = ttk.Combobox(
            audio_frame,
            values=list(self.available_sample_formats[
                self.parent.audio_system].keys()),
            state="readonly")
        self.sample_format.set(self.parent.sample_format)
        if self.sample_format.get() not in self.sample_format["values"]:
            self.sample_format.set("Automatic")
        self.sample_format.bind("<<ComboboxSelected>>",
                                self.update_audio_values)
        self.sample_format.grid(row=2, column=1,sticky="ew")

        ttk.Label(audio_frame, text="Sample Rate:").grid(
            row=3, column=0, sticky="w")
        self.sample_rate = ttk.Combobox(
            audio_frame,
            values=("Automatic", "8000 Hz", "44100 Hz", "48000 Hz", "88200 Hz",
                    "96000 Hz"),
            state="readonly",
        )
        self.sample_rate.set(self.parent.sample_rate)
        self.sample_rate.bind("<<ComboboxSelected>>",
                              self.update_audio_values)
        self.sample_rate.grid(row=3, column=1, sticky="ew")

        self.hq_resampling_var = tk.BooleanVar()
        self.hq_resampling_var.set(self.parent.hq_resampling)
        self.hq_resampling = ttk.Checkbutton(
            audio_frame,
            text="High-Quality Resampling",
            variable=self.hq_resampling_var,
            command=self.update_audio_values,
            onvalue=True,
            offvalue=False
        )
        self.hq_resampling.grid(row=4, column=1, sticky="ew")

        audio_frame.columnconfigure(1, weight=1)
        for child in audio_frame.winfo_children():
            child.grid_configure(padx=padding/2, pady=padding/4)

        # Advanced
        advanced_frame = ttk.LabelFrame(self.frame,
                                        text="Advanced",
                                        padding=(padding/2, padding/4*3))
        advanced_frame.pack(fill="x", padx=padding, pady=padding)
        ttk.Button(advanced_frame, text="Open Configuration Folder",
                   command=self.open_config_folder).grid(
            row=0, column=0, sticky="w",)
        ttk.Button(advanced_frame, text="Reset Configuration...",
                   command=self.reset_config).grid(
            row=0, column=1, sticky="w",)


    def on_show(self):
        self.update_audio_values()

    def update_audio_values(self, event=None):
        restart_player = False

        audio_system = self.audio_system.get()
        sample_format = self.sample_format.get()
        sample_rate = self.sample_rate.get()
        channel_mode = self.channel_mode.get()
        hq_resampling = self.hq_resampling_var.get()

        if audio_system != self.parent.audio_system:
            sample_formats = \
                list(self.available_sample_formats[audio_system].keys())
            self.sample_format["values"] = sample_formats
            self.parent.apply_setting("AUDIO", "audio_system", audio_system)
            if sample_format not in sample_formats:
                sample_format = "Automatic"
                self.sample_format.set(sample_format)
                self.parent.apply_setting("AUDIO", "sample_format",
                                          sample_format)
            restart_player = True

        if sample_format != self.parent.sample_format:
            self.parent.apply_setting("AUDIO", "sample_format", sample_format)
            restart_player = True

        if sample_rate != self.parent.sample_rate:
            self.parent.apply_setting("AUDIO", "sample_rate", sample_rate)
            restart_player = True

        if channel_mode != self.parent.channel_mode:
            self.parent.apply_setting("AUDIO", "channel_mode", channel_mode)
            restart_player = True

        if hq_resampling != self.parent.hq_resampling:
            self.parent.apply_setting("AUDIO", "hq_resampling", hq_resampling)
            restart_player = True

        if restart_player:
            self.parent.restart_player()

        if sample_rate == "Automatic":
            self.hq_resampling.state(["disabled"])
        else:
            self.hq_resampling.state(["!disabled"])

    def open_config_folder(self):
        config_folder = get_config_folder()
        if not os.path.exists(config_folder):
            os.makedirs(config_folder)
        if platform.system() == "Windows":
            os.startfile(config_folder)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", config_folder])
        else:
            subprocess.Popen(["xdg-open", config_folder])

    def reset_config(self):
        msg = ("This will delete all user configuration and close the"
               "application!\n\n Continue?")

        if messagebox.askyesno("Reset Configuration", msg, icon='warning',
                               parent=self):
            config_folder = get_config_folder()
            try:
                shutil.rmtree(config_folder)
                os.makedirs(config_folder)
            except Exception as e:
                messagebox.showerror(
                    "Error", f'Could not delete data in "{config_folder}"!')
            self.parent.parent.destroy()

class CreateAlbumDialogue(DialogueWindow):
    TITLE = "Create Zipped Album"

    def create_widgets(self):
        self.directory = tk.StringVar()
        self.directory.trace_add("write", self.change_create_state)
        self.filename = tk.StringVar()
        self.filename.trace_add("write", self.change_create_state)
        self.png = tk.BooleanVar(value=False)
        self.png.set(self.parent.config_parser.getboolean(
            "CREATE", "as_png", fallback=False))
        self.png.trace_add("write", self.change_png)
        self.open_album = tk.BooleanVar()
        self.open_album.set(self.parent.config_parser.getboolean(
            "CREATE", "open_album", fallback=True))
        self.open_album.trace_add("write", self.change_open_album)

        padding = self.parent.padding
        frame = ttk.Frame(self)
        frame.pack()

        style = ttk.Style()
        style.configure("TLabelframe.Label",
                        font=self.parent.default_fonts.spec(weight="bold"))

        input_frame = ttk.LabelFrame(frame, text="Input",
                                     padding=(padding/2, padding/4*3))
        input_frame.pack(fill="x", padx=padding, pady=(padding, 0))
        dir_label = ttk.Label(input_frame, text="Source Folder:").grid(
            row=0, column=0, sticky="w")
        self.dir_entry = ttk.Entry(input_frame, textvariable=self.directory,
                                   width=50)
        self.dir_entry.grid(row=1, column=0, sticky="ew")
        self.dir_button = ttk.Button(input_frame, text="Browse...",
                                     command=self.browse_in)
        self.dir_button.grid(row=1, column=1, sticky="e")
        input_frame.columnconfigure(1, weight=1)
        for child in input_frame.winfo_children():
            child.grid_configure(padx=padding/2, pady=padding/4)

        output_frame = ttk.LabelFrame(frame, text="Output",
                                     padding=(padding/2, padding/4*3))
        output_frame.pack(fill="x", padx=padding, pady=(padding, 0))
        filename_label = ttk.Label(output_frame, text="Target File:").grid(
            row=0, column=0, sticky="w")
        filename_entry = ttk.Entry(output_frame, textvariable=self.filename,
                                   width=50)
        filename_entry.grid(row=1, column=0, sticky="ew")
        ttk.Button(output_frame, text="Browse...",
                   command=self.browse_out).grid(row=1, column=1, sticky="e")
        ttk.Checkbutton(output_frame,
                        text='Wrap in album sleeve (.zlbm.png)',
                        variable=self.png).grid(row=2, column=0, sticky="w",
                                                columnspan=3)
        output_frame.columnconfigure(1, weight=1)
        for child in output_frame.winfo_children():
            child.grid_configure(padx=padding/2, pady=padding/4)

        button_frame = ttk.Frame(frame, padding=(padding/2, padding/4*3))
        button_frame.pack(fill="x")
        ttk.Checkbutton(button_frame,
                        text="Open album after creation",
                        variable=self.open_album).grid(
                            row=0, column=0, sticky="w")
        self.create_button = ttk.Button(button_frame, text="Create",
                                        command=self.create,
                                        default="active",
                                        state="disabled")
        cancel_button = ttk.Button(button_frame, text="Cancel",
                                   command=self.close)
        # Cross-platform button ordering
        if platform.system() in ("Darwin", "Linux"): # Cancel | Create
            cancel_button.grid(row=0, column=1, sticky="e")
            self.create_button.grid(row=0, column=2, sticky="e")
        else: # Create | Cancel
            self.create_button.grid(row=0, column=1, sticky="e")
            cancel_button.grid(row=0, column=2, sticky="e")
        button_frame.columnconfigure(0, weight=1)
        for child in button_frame.winfo_children():
            child.grid_configure(padx=padding/2, pady=padding/4)

    def on_show(self):
        self.dir_entry.focus_set()
        self.bind('<Return>', (lambda e, b=self.dir_button: b.invoke()))

    def browse_in(self):
        try:
            initialdir = os.path.split(self.directory.get())[0]
            assert os.path.isdir(initialdir)
        except AssertionError:
            initialdir = self.parent.config_parser.get(
                "CREATE", "last_input_directory",
                fallback=os.path.expanduser("~"))
        parent = None if platform.system() == "Darwin" else self
        directory = filedialog.askdirectory(initialdir=initialdir,
                                            mustexist=True,
                                            parent=parent)
        self.focus_force()
        if directory:
            self.directory.set(directory)
            if not self.filename.get():
                ext = ".zlbm"
                if self.png.get():
                    ext += ".png"
                self.filename.set(directory + ext)
            if not self.parent.config_parser.has_section("CREATE"):
                self.parent.config_parser.add_section("CREATE")
            self.parent.config_parser.set("CREATE", "last_input_directory",
                                          directory)

    def browse_out(self):
        try:
            initialdir = os.path.split(self.filename.get())[0]
            assert os.path.isdir(initialdir)
        except AssertionError:
            initialdir = self.parent.config_parser.get(
                    "CREATE", "last_output_directory",
                fallback=os.path.expanduser("~"))
        parent = None if platform.system() == "Darwin" else self
        filename = filedialog.asksaveasfilename(initialdir=initialdir,
                                                defaultextension=".zlbm",
                                                parent=parent)
        self.focus_force()
        if filename:
            if self.png.get():
                filename += ".png"
            self.filename.set(filename)
            if not self.parent.config_parser.has_section("CREATE"):
                self.parent.config_parser.add_section("CREATE")
            self.parent.config_parser.set("CREATE", "last_output_directory",
                                          os.path.split(filename)[0])

    def change_png(self, *args):
        filename = self.filename.get()
        png = self.png.get()
        if png:
            if filename:
                    self.filename.set(
                        os.path.splitext(filename)[0] + ".zlbm.png")
        else:
            if filename:
                if filename.endswith(".zlbm.png"):
                    self.filename.set(filename[:-4])
                else:
                    self.filename.set(os.path.splitext(filename)[0] + ".zlbm")
        if not self.parent.config_parser.has_section("CREATE"):
            self.parent.config_parser.add_section("CREATE")
        self.parent.config_parser.set("CREATE", "as_png", str(int(png)))

    def change_open_album(self, *args):
        if not self.parent.config_parser.has_section("CREATE"):
            self.parent.config_parser.add_section("CREATE")
        self.parent.config_parser.set("CREATE", "open_album",
                                      str(int(self.open_album.get())))


    def create(self):
        self.close()
        self.parent.make_album(self.directory.get(),
                               self.filename.get(),
                               self.png.get(),
                               self.open_album.get())

    def change_create_state(self, *args):
        if self.directory.get() and self.filename.get():
            self.create_button["state"] = "normal"
            self.bind('<Return>', (lambda e, b=self.create_button: b.invoke()))
        else:
            self.create_button["state"] = "disabled"


