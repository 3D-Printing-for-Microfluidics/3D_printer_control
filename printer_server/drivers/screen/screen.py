"""Screen module."""
import atexit
import tkinter
import logging
import threading
from PIL import Image, ImageTk


class Screen:
    """Create and manage a new Tk window."""

    def __init__(self, resolution, screen_offset=0, log_level=logging.DEBUG):
        """ Initialize a new screen object.

        resolution: The (width, height) resolution of the screen
        screen_offset: How far to the right to offset this screen by.
            This is only used if there are multiple screens, where the
            offset of the current screen is the sum of the widths of all
            previous screens.
        """
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.width, self.height = resolution
        self.root = tkinter.Toplevel()

        self.root.attributes("-fullscreen", True)
        self.root.geometry(f"{self.width}x{self.height}+{screen_offset}+0")
        self.root.config(cursor="none")
        self.root.focus_set()
        self.root.wm_attributes("-topmost", 1)

        self.canvas = tkinter.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bd=0,
            highlightthickness=0,
            relief="ridge",
        )
        self.canvas.pack()
        self.canvas.configure(background="black")
        self.canvasImage = self.canvas.create_image(0, 0, anchor=tkinter.NW)
        self.tkImage = None

    def draw(self, fn):
        """Draw image in the Tk canvas."""

        self.log.info("Drawing %s", fn)
        try:
            pilImage = Image.open(fn)
        except (OSError, FileNotFoundError):
            self.log.warning("Image not found, drawing white")
            pilImage = Image.new(mode="L", size=(self.width, self.height), color=255)
        self.tkImage = ImageTk.PhotoImage(pilImage)
        self.canvas.itemconfig(self.canvasImage, image=self.tkImage)
        self.root.update()

    def clear(self):
        """Clear the Tk window by drawing a black image."""
        self.log.info("Clearing virtual screen")
        pilImage = Image.new(mode="L", size=(self.width, self.height), color=0)
        self.tkImage = ImageTk.PhotoImage(pilImage)
        self.canvas.itemconfig(self.canvasImage, image=self.tkImage)
        self.root.update()


class ScreenThread(threading.Thread):
    """Create and manage a thread to control the Tk windows."""

    def __init__(self, resolutions=((2560, 1600), None), log_level=logging.DEBUG):
        super().__init__(daemon=True)
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.resolutions = resolutions
        self.total_offset = 0
        self.screens = None
        self.log_level = log_level

    def run(self):
        """Create a Tk window and run it."""

        self.screens = []
        for resolution in self.resolutions:
            if resolution is not None:
                self.screens.append(Screen(resolution, self.total_offset, self.log_level))
                self.total_offset += resolution[0]
        atexit.register(self.stop)
        tkinter.mainloop()

    def stop(self):
        """Stop the thread."""
        for screen in self.screens:
            screen.root.quit()

    def draw(self, fn, screen=0):
        """Draw an image to the specified screen."""

        try:
            self.screens[screen].draw(fn)
        except IndexError:
            self.log.error("Screen %s does not exist", screen)

    def clear(self, screen=0):
        """Clear the specified screen."""
        try:
            self.screens[screen].clear()
        except IndexError:
            self.log.error("Screen %s does not exist", screen)
