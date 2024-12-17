"""Screen module."""
import atexit
import base64
import tkinter
import logging
import threading
from io import BytesIO
from printer_server.threading_wrapper import Thread
from PIL import Image, ImageTk


class Screen:
    """Create and manage a new Tk window."""

    def __init__(self, resolution, screen_offset=0, log_level=logging.DEBUG):
        """Initialize a new screen object.

        resolution: The (width, height) resolution of the screen
        screen_offset: How far to the right to offset this screen by.
            This is only used if there are multiple screens, where the
            offset of the current screen is the sum of the widths of all
            previous screens.
        """
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.image = None
        self.tk_image = None
        self.resolution = resolution
        self.window = tkinter.Toplevel()

        self.window.attributes("-fullscreen", True)
        self.window.geometry(f"{resolution[0]}x{resolution[1]}+{screen_offset}+0")
        self.window.config(cursor="none")
        self.window.focus_set()
        self.window.wm_attributes("-topmost", 1)

        self.canvas = tkinter.Canvas(
            self.window,
            width=resolution[0],
            height=resolution[1],
            bd=0,
            highlightthickness=0,
            relief="ridge",
        )
        self.canvas.pack()
        self.canvas.configure(background="black")
        self.canvas_image = self.canvas.create_image(0, 0, anchor=tkinter.NW)

    def draw(self, img_path):
        """Draw image in the Tk canvas."""
        try:
            self.image = Image.open(img_path)
        except (OSError, FileNotFoundError):
            self.log.warning("Image not found, drawing white")
            self.image = Image.new(mode="L", size=self.resolution, color=255)
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.canvas.itemconfig(self.canvas_image, image=self.tk_image)
        self.window.update()

        # It takes about 200ms to change the screen
        time.sleep(0.25)

    def clear(self):
        """Clear the Tk window by drawing a black image."""
        self.image = Image.new(mode="L", size=self.resolution, color=0)
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.canvas.itemconfig(self.canvas_image, image=self.tk_image)
        self.window.update()

        # It takes about 200ms to change the screen
        time.sleep(0.25)

    def fetch_preview(self, scale=1/20):
        new_size = (int(self.resolution[0] * scale), int(self.resolution[1] * scale))
        if self.image is not None:
            img = self.image.resize(new_size, Image.LANCZOS)
        else:
            img = Image.new(mode="L", size=new_size, color=0)
        

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)  # Adjust quality if needed (1-100)
        buffer.seek(0)

        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return img_base64


class ScreenThread(Thread):
    """Create and manage a thread to control the Tk windows."""

    def __init__(
        self, config_dict=None, resolutions=((2560, 1600), None), log_level=logging.DEBUG
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        super().__init__(self.log, name="ScreenThread", daemon=True)
        self.light_engines = config_dict["light_engines"]
        self.resolutions = resolutions
        self.total_offset = None
        self.screens = None
        self.log_level = log_level

    def run(self):
        """Create a Tk window and run it."""
        self.log.info("Starting screen thread")
        self.screens = []
        self.total_offset = 0
        for resolution in self.resolutions:
            if resolution is not None:
                self.screens.append(Screen(resolution, self.total_offset, self.log_level))
                self.total_offset += resolution[0]
        atexit.register(self.stop)
        tkinter.mainloop()
        self.log.info("Screen thread closed")

    def stop(self):
        """Stop the thread."""
        if self.screens is not None:
            self.log.info("Stopping screen thread")
            for screen in self.screens:
                screen.window.quit()
            self.screens = None

    def draw(self, img_path, screen=0):
        """Draw an image to the specified screen."""
        self.log.info("Drawing %s to screen %s", img_path, screen)
        try:
            self.screens[screen].draw(img_path)
        except IndexError:
            self.log.error("Screen %s does not exist", screen)

    def clear(self, screen=0):
        """Clear the specified screen."""
        self.log.info("Clearing screen %s", screen)
        try:
            self.screens[screen].clear()
        except IndexError:
            self.log.error("Screen %s does not exist", screen)

    def fetch_preview(self, screen=0):
        try:
            return self.screens[screen].fetch_preview()
        except IndexError:
            self.log.error("Screen %s does not exist", screen)

    def getScreenNumber(self, light_engine):
        if light_engine in self.light_engines:
            return self.light_engines.index(light_engine)
        else:
            return -1
