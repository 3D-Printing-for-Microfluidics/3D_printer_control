# -*- coding: utf-8 -*-
"""
Visitech screen module
=======================
"""
# `mttkinter` stands for multi-threading tkinter.
# The `tkinter` in standard library is not technically thread-safe.
# `mttkinter` wraps it to make it thread-safe.
import atexit
import tkinter
import logging
import threading
from PIL import Image, ImageTk


class Screen:
    """The Screen class uses ``tkinter`` as the underlying
    windowing framework, because ``tkinter`` is part of the
    Python standard library, and it is platform agnostic.
    Most importantly, it works.
    """

    def __init__(self, resolution, screen_offset=0, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.width, self.height = resolution
        self.root = tkinter.Toplevel()
        # Uncomment the following line to get a fullscreen window
        self.root.attributes("-fullscreen", True)

        # set the size and position of Tk window
        # format: <width>x<height>+xoffset+yoffset
        self.root.geometry(f"{self.width}x{self.height}+{screen_offset}+0")
        # hide cursor in the Tk window
        self.root.config(cursor="none")
        self.root.focus_set()
        # set tk window on top
        self.root.wm_attributes("-topmost", 1)

        # create a canvas object where we draw images of each 3D print layer
        self.canvas = tkinter.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bd=0,  # border width
            highlightthickness=0,  # canvas edge with
            relief="ridge",
        )
        # set the canvas position in tk window
        self.canvas.pack()
        # set the canvas background to be black
        self.canvas.configure(background="black")
        # create a canvas image, offset (0, 0),
        # anchor point NW (northwest), upper left corner
        self.canvasImage = self.canvas.create_image(0, 0, anchor=tkinter.NW)
        self.tkImage = None

    def draw(self, fn):
        """Draw image in the Tk canvas.
        :param str fn: image filename
        """
        # open image file as a PIL.Image object. If it is a corrupted image,
        # substitute it with a plain white image.
        self.log.info("Drawing %s", fn)
        try:
            pilImage = Image.open(fn)
        except (OSError, FileNotFoundError):
            self.log.warning("Image not found, drawing white")
            pilImage = Image.new(mode="L", size=(self.width, self.height), color=255)
        # Tk canvas only takes `PhotoImage` object
        self.tkImage = ImageTk.PhotoImage(pilImage)
        # change the canvas image to the new image
        # In order to update the Tk window, we still need to call
        # `root.update`, which is done in the `ScreenThread`.
        self.canvas.itemconfig(self.canvasImage, image=self.tkImage)
        self.root.update()

    def clear(self):
        """Clear the Tk window by drawing a black image."""
        # When mode is `1`, it creates a 1-bit image.
        self.log.info("Clearing virtual screen")
        pilImage = Image.new(mode="L", size=(self.width, self.height), color=0)
        self.tkImage = ImageTk.PhotoImage(pilImage)
        self.canvas.itemconfig(self.canvasImage, image=self.tkImage)
        self.root.update()


class ScreenThread(threading.Thread):
    """A subclass of ``threading.Thread``. The Tk window is
    created and runs in this thread.

    .. py:attribute:: stopped

        a ``threading.Event`` object to set flag to stop thread
    """

    def __init__(self, resolutions=((2560, 1600), None), log_level=logging.DEBUG):
        super().__init__(daemon=True)
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.resolutions = resolutions
        self.total_offset = 0
        self.screens = None
        self.log_level = log_level

    def run(self):
        """Create a Tk window and run it. Instead of the normal
        ``root.mainloop`` in tkinter, a custom while-loop is
        implemented such that it can be stopped easily and
        arbitrary operation can be added, such as guaranteeing
        the tk window is on top.
        """
        self.screens = []
        for resolution in self.resolutions:
            if resolution is not None:
                self.screens.append(Screen(resolution, self.total_offset, self.log_level))
                self.total_offset += resolution[0]
        atexit.register(self.stop)
        tkinter.mainloop()

    def stop(self):
        """Stop the thread"""
        for screen in self.screens:
            screen.root.quit()

    def draw(self, fn, screen=0):
        try:
            self.screens[screen].draw(fn)
        except IndexError:
            self.log.error("Screen %s does not exist", screen)

    def clear(self, screen=0):
        try:
            self.screens[screen].clear()
        except IndexError:
            self.log.error("Screen %s does not exist", screen)
