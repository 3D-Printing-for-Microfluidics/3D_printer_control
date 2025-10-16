"""Screen module."""
import time
import atexit
import base64
import tkinter
import logging
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageTk

from printer_server.settings import Config
from printer_server.threading_wrapper import Thread

class Screen:
    """Create and manage a new Tk window."""

    def __init__(self, resolution, light_correction_paths, dark_correction_paths, screen_offset=0, log_level=logging.DEBUG):
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
        self.image_path = None
        self.led_num = 0
        self.do_light_correction = False
        self.do_dark_correction = False
        self.light_correction_paths = light_correction_paths
        self.dark_correction_paths = dark_correction_paths
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

    def draw(self, img_path, led_num=0):
        """Draw image in the Tk canvas."""
        try:
            self.led_num = led_num
            self.image = Image.open(img_path)
            if self.do_light_correction and self.light_correction_paths[led_num] is not None:
                mask = self.image
                correction = Image.open(self.light_correction_paths[led_num])
                self.image = Image.composite(correction, mask, mask=mask)
            if self.do_dark_correction and self.dark_correction_paths[led_num] is not None:
                dark_correction = Image.open(self.dark_correction_paths[led_num])
                mask = Image.eval(self.image, lambda x: 255 if x == 0 else 0)
                self.image = Image.composite(dark_correction, self.image, mask=mask)
            self.image_path = img_path

        except (OSError, FileNotFoundError):
            self.log.warning("Image not found, drawing white")
            self.log.info("\t%s", img_path)
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
        self.image_path = None
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
        self, config_dict=None, log_level=logging.DEBUG
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        super().__init__(self.log, name="ScreenThread", daemon=True)
        self.config_dict = config_dict
        self.light_engines = config_dict["light_engines"]
        self.total_offset = None
        self.screens = None
        self.log_level = log_level

    def _getScreenIndex(self, light_engine):
        if light_engine in self.light_engines:
            return self.light_engines.index(light_engine)
        else:
            return -1

    def run(self):
        """Create a Tk window and run it."""
        self.log.info("Starting screen thread")

        self.screens = []
        self.total_offset = 0
        for le in self.light_engines:
            light_correction_paths = []
            dark_correction_paths = []
            for led in range(len(self.config_dict[le]["leds_nm"])):
                correction_directory= Path(Config.PRINT_SERVER_FOLDER) / Path("grayscale_correction_data")
                try:
                    light_correction_image = Path(self.config_dict[le]["light_grayscale_correction_image"][led])
                    light_correction_paths.append(correction_directory / light_correction_image)
                except:
                    light_correction_paths.append(None)
                try:
                    dark_correction_image = Path(self.config_dict[le]["dark_grayscale_correction_image"][led])
                    dark_correction_paths.append(correction_directory / dark_correction_image)
                except:
                    dark_correction_paths.append(None)
            
            resolution = tuple(self.config_dict[le]["resolution"])
            self.screens.append(Screen(resolution, light_correction_paths, dark_correction_paths, screen_offset=self.total_offset, log_level=self.log_level))
            self.total_offset += resolution[0]

        atexit.register(self.stop)
        tkinter.mainloop()
        self.log.info("Screen thread closed")

    def setCorrectionEnable(self, light_enable, dark_enable, light_engine="visitech"):
        screen = self._getScreenIndex(light_engine)
        try:         
            prev_light_val = self.screens[screen].do_light_correction
            prev_dark_val = self.screens[screen].do_dark_correction
            self.screens[screen].do_light_correction = light_enable
            self.screens[screen].do_dark_correction = dark_enable
            if (prev_light_val != light_enable or prev_dark_val != dark_enable) and self.screens[screen].image_path is not None:
                self.draw(self.screens[screen].image_path, light_engine=light_engine, led_num=self.screens[screen].led_num)
                
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)
            return
        
    def getLightCorrectionEnable(self, light_engine="visitech"):
        screen = self._getScreenIndex(light_engine)
        try:
            return self.screens[screen].do_light_correction
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)
            return False
        
    def getDarkCorrectionEnable(self, light_engine="visitech"):
        screen = self._getScreenIndex(light_engine)
        try:
            return self.screens[screen].do_dark_correction
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)
            return False

    def stop(self):
        """Stop the thread."""
        if self.screens is not None:
            self.log.info("Stopping screen thread")
            for screen in self.screens:
                screen.window.quit()
            self.screens = None

    def draw(self, img_path, light_engine="visitech", led_num=0):
        """Draw an image to the specified screen."""
        screen = self._getScreenIndex(light_engine)
        self.log.info("Drawing %s to %s (screen %s)", Path(img_path).name, light_engine, screen)
        if self.getLightCorrectionEnable(light_engine):
            if self.screens[screen].light_correction_paths[led_num] is None:
                self.log.warning("Light correction image %s missing", Path(self.screens[screen].light_correction_paths[led_num]).name)
            else:
                self.log.info("\tLight correction image: %s", Path(self.screens[screen].light_correction_paths[led_num]).name)
        if self.getDarkCorrectionEnable(light_engine):
            if self.screens[screen].dark_correction_paths[led_num] is None:
                self.log.warning("Dark correction image %s missing", Path(self.screens[screen].dark_correction_paths[led_num]).name)
            else:
                self.log.info("\tDark correction image: %s", Path(self.screens[screen].dark_correction_paths[led_num]).name)

        trys = 3 # very occationally the screen will fail to find the image. Not sure why, but hopefully this will fix it
        for i in range(trys):
            try:
                self.screens[screen].draw(img_path, led_num=led_num)
                break
            except IndexError:
                if i != trys - 1:
                    self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)
            except AssertionError:
                if i != trys - 1:
                    self.log.error("Screen for %s (screen %s) failed to load image", light_engine, screen)
            time.sleep(0.1)

    def clear(self, light_engine="visitech"):
        """Clear the specified screen."""
        screen = self._getScreenIndex(light_engine)
        self.log.info("Clearing screen %s", screen)
        try:
            self.screens[screen].clear()
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)

    def fetch_preview(self, light_engine="visitech"):
        screen = self._getScreenIndex(light_engine)
        try:
            return self.screens[screen].fetch_preview()
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)