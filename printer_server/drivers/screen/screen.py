"""Screen module."""
import time
import atexit
import base64
import tkinter
import logging
import threading
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageTk

from printer_server.settings import Config
from printer_server.threading_wrapper import Thread

class Screen:
    """Create and manage a new Tk window."""

    def __init__(
            self, 
            resolution, 
            correction_paths, 
            screen_offset=0, 
            mirror_short_axis=False, 
            mirror_long_axis=False, 
            log_level=logging.DEBUG
        ):
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
        self.image_preview = None
        self.tk_image = None
        self.image_path = None
        self.led_num = 0
        self.do_correction = False
        self.mirror_short = False
        self.mirror_long = False
        self.correction_paths = correction_paths
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

        self.config_mirror_short_axis = mirror_short_axis
        self.config_mirror_long_axis = mirror_long_axis

    def draw(self, img_path, led_num=0, mirror_short=False, mirror_long=False, _grayscale_correction_path=None):
        """Draw image in the Tk canvas."""
        try:
            self.image_path = img_path
            self.led_num = led_num
            self.mirror_short = mirror_short
            self.mirror_long = mirror_long
            self.image = Image.open(img_path)

            # xor class and local variable
            # we do this on a software rather then a hardware level, because not all le support mirroring long axis
            _mirror_short = mirror_short != self.config_mirror_short_axis
            _mirror_long = mirror_long != self.config_mirror_long_axis

            self.image_preview = self.image.copy()
            if _mirror_short and _mirror_long:
                self.image = self.image.transpose(Image.ROTATE_180)
            elif _mirror_short:
                self.image = self.image.transpose(Image.FLIP_TOP_BOTTOM)
            elif _mirror_long:
                self.image = self.image.transpose(Image.FLIP_LEFT_RIGHT)

            if self.do_correction and (self.correction_paths[led_num] is not None or _grayscale_correction_path is not None):
                mask = self.image
                if _grayscale_correction_path is not None:
                    correction = Image.open(_grayscale_correction_path)
                else:
                    correction = Image.open(self.correction_paths[led_num])
                self.image = Image.composite(correction, mask, mask=mask)

        except (OSError, FileNotFoundError):
            self.log.warning("Image not found, drawing white (%s)", img_path)
            self.log.info("\t%s", img_path)
            self.image = Image.new(mode="L", size=self.resolution, color=255)
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.canvas.itemconfig(self.canvas_image, image=self.tk_image)
        self.window.update()

        # It takes about 200ms to change the screen
        time.sleep(0.25)

    def fetch_preview(self, scale=1/20):
        new_size = (int(self.resolution[0] * scale), int(self.resolution[1] * scale))
        if self.image_preview is not None:
            img = self.image_preview.resize(new_size, Image.LANCZOS)
        else:
            img = Image.new(mode="L", size=new_size, color=0)
        

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)  # Adjust quality if needed (1-100)
        buffer.seek(0)

        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return img_base64
    
    def get_image(self):
        return self.image_path


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
        self.screen_draw_info = None
        self.log_level = log_level
        self._stop_requested = threading.Event()
        self._reset_requested = threading.Event()

    def _getScreenIndex(self, light_engine):
        if light_engine in self.light_engines:
            return self.light_engines.index(light_engine)
        else:
            return -1

    def run(self):
        """Create a Tk window and run it."""
        self.log.info("Starting screen thread")
        atexit.register(self.stop)
        self._stop_requested.clear()
        self._reset_requested.clear()

        while True:
            self.screens = []
            self.total_offset = 0
            for le in self.light_engines:
                correction_paths = []
                for led in range(len(self.config_dict[le]["leds_nm"])):
                    correction_directory= Path(Config.PRINT_SERVER_FOLDER) / Path("grayscale_correction_data")
                    try:
                        correction_image = Path(self.config_dict[le]["grayscale_correction_image"][led])
                        correction_paths.append(correction_directory / correction_image)
                    except:
                        correction_paths.append(None)
                
                resolution = tuple(self.config_dict[le]["resolution"])
                self.screens.append(
                    Screen(
                        resolution, 
                        correction_paths, 
                        screen_offset=self.total_offset, 
                        mirror_short_axis=self.config_dict[le].get("mirror_short_axis", False), 
                        mirror_long_axis=self.config_dict[le].get("mirror_long_axis", False), 
                        log_level=self.log_level
                    )
                )
                self.total_offset += resolution[0]
            if self.screen_draw_info is not None:
                for screen, (img_path, led_num, mirror_short, mirror_long) in zip(self.screens, self.screen_draw_info):
                    screen.draw(img_path, led_num=led_num, mirror_short=mirror_short, mirror_long=mirror_long)

            tkinter.mainloop()

            if self._reset_requested.is_set() and not self._stop_requested.is_set():
                self._reset_requested.clear()
                continue
            break

        self.log.info("Screen thread closed")

    def setCorrectionEnable(self, enable, light_engine="visitech"):
        screen = self._getScreenIndex(light_engine)
        try:         
            prev_val = self.screens[screen].do_correction
            self.screens[screen].do_correction = enable
            if (prev_val != enable) and self.screens[screen].image_path is not None:
                self.draw(self.screens[screen].image_path, light_engine=light_engine, led_num=self.screens[screen].led_num)
                
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)
            return
        
    def getCorrectionEnable(self, light_engine="visitech"):
        screen = self._getScreenIndex(light_engine)
        try:
            return self.screens[screen].do_correction
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)
            return False
        

    def stop(self, restart=False):
        """Stop the thread."""
        if self.screens is not None:
            self.log.info("Stopping screen thread")
            if restart:
                self._reset_requested.set()
                self.screen_draw_info = []
                for screen in self.screens:
                    self.screen_draw_info.append((screen.image_path, screen.led_num, screen.mirror_short, screen.mirror_long))
            else:
                self._stop_requested.set()

            for screen in self.screens:
                screen.window.destroy()
            root = tkinter._default_root
            root.after(10, root.destroy)
            self.screens = None


    def draw(self, img_path, light_engine="visitech", led_num=0, mirror_short=False, mirror_long=False, _grayscale_correction_path=None):
        """Draw an image to the specified screen."""
        screen = self._getScreenIndex(light_engine)
        self.log.info("Drawing %s to %s (screen %s)", Path(img_path).name, light_engine, screen)
        if self.getCorrectionEnable(light_engine):
            if self.screens[screen].correction_paths[led_num] is None and _grayscale_correction_path is None:
                self.log.warning("Correction image %s missing", Path(self.screens[screen].correction_paths[led_num]).name)
            else:
                if _grayscale_correction_path is not None:
                    self.log.info("\tInternal Correction image: %s", Path(_grayscale_correction_path).name)
                else:
                    self.log.info("\tCorrection image: %s", Path(self.screens[screen].correction_paths[led_num]).name)

        trys = 3 # very occationally the screen will fail to find the image. Not sure why, but hopefully this will fix it
        for i in range(trys):
            try:
                self.screens[screen].draw(
                    img_path,
                    led_num=led_num,
                    mirror_short=mirror_short,
                    mirror_long=mirror_long,
                    _grayscale_correction_path=_grayscale_correction_path
                )
                break
            except IndexError:
                if i != trys - 1:
                    self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)
            except AssertionError:
                if i != trys - 1:
                    self.log.error("Screen for %s (screen %s) failed to load image", light_engine, screen)
            time.sleep(0.1)

    def fetch_preview(self, light_engine="visitech", scale=1/20):
        screen = self._getScreenIndex(light_engine)
        try:
            return self.screens[screen].fetch_preview(scale=scale)
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)

    def get_image(self, light_engine="visitech"):
        screen = self._getScreenIndex(light_engine)
        try:
            return self.screens[screen].get_image()
        except IndexError:
            self.log.error("Screen for %s (screen %s) does not exist", light_engine, screen)