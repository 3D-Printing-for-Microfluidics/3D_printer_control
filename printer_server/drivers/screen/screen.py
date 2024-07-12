# ####### QT5 #######

# import atexit
# import logging
# from printer_server.threading_wrapper import Thread
# from PIL import Image
# from PyQt5 import QtCore, QtGui, QtWidgets


# class Screen(QtWidgets.QWidget):
#     """Create and manage a new Qt window."""

#     def __init__(self, resolution, monitor_index=0, log_level=logging.DEBUG):
#         """Initialize a new screen object.

#         resolution: The (width, height) resolution of the screen
#         monitor_index: Index of the monitor where this screen should be displayed.
#         """
#         super().__init__()
#         self.log = logging.getLogger(__name__)
#         self.log.setLevel(log_level)
#         self.image = None
#         self.resolution = resolution

#         self.setWindowTitle("Screen")
#         self.setGeometry(0, 0, resolution[0], resolution[1])
#         self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
#         self.setCursor(QtCore.Qt.BlankCursor)
#         # self.showFullScreen()
#         self.show()

#         # Position the window based on the monitor index
#         self.monitor_index = monitor_index
#         self.position_window()
#         self.update()
        
#     def position_window(self):
#         """Position the window based on the monitor index."""
#         app = QtWidgets.QApplication.instance()
#         print(app.screens())
#         screen = app.screens()[self.monitor_index]
#         geometry = screen.geometry()
#         self.move(geometry.x(), geometry.y())
#         print(geometry.x(), geometry.y(), geometry.width(), geometry.height())

#     def paintEvent(self, event):
#         """Handle the paint event."""
#         painter = QtGui.QPainter(self)
#         if self.image:
#             pixmap = QtGui.QPixmap(self.image)
#             painter.drawPixmap(self.rect(), pixmap)

#     def draw(self, img_path):
#         """Draw image in the Qt window."""
#         try:
#             self.image = img_path
#             self.update()
#         except (OSError, FileNotFoundError):
#             self.log.warning("Image not found, drawing white")
#             self.image = None
#             self.update()

#     def clear(self):
#         """Clear the Qt window by drawing a black image."""
#         self.image = None
#         self.update()


# class ScreenThread(Thread):
#     """Create and manage a thread to control the Qt windows."""

#     def __init__(
#         self, config_dict=None, resolutions=((2560, 1600), None), log_level=logging.DEBUG
#     ):
#         self.log = logging.getLogger(__name__)
#         self.log.setLevel(log_level)
#         super().__init__(self.log, name="ScreenThread", daemon=True)
#         self.light_engines = config_dict["light_engines"]
#         self.resolutions = resolutions
#         self.screens = []
#         self.log_level = log_level
#         self.app = None

#     def run(self):
#         """Create Qt windows and run the main loop."""
#         self.log.info("Starting screen thread")

#         self.app = QtWidgets.QApplication([])

#         screens = self.app.screens()
#         n_monitors = len(screens)
#         self.log.info("Number of monitors detected: %d", n_monitors)

#         for i, resolution in enumerate(self.resolutions):
#             if resolution is not None and i < n_monitors:
#                 self.screens.append(Screen(resolution, i, self.log_level))

#         atexit.register(self.stop)
#         self.app.exec_()

#     def stop(self):
#         """Stop the thread."""
#         if self.screens is not None:
#             self.log.info("Stopping screen thread")
#             for screen in self.screens:
#                 screen.close()
#             self.screens = None

#     def draw(self, img_path, screen=0):
#         """Draw an image to the specified screen."""
#         self.log.info("Drawing %s to screen %s", img_path, screen)
#         try:
#             self.screens[screen].draw(img_path)
#         except IndexError:
#             self.log.error("Screen %s does not exist", screen)

#     def clear(self, screen=0):
#         """Clear the specified screen."""
#         self.log.info("Clearing screen %s", screen)
#         try:
#             self.screens[screen].clear()
#         except IndexError:
#             self.log.error("Screen %s does not exist", screen)

# ####### GTK #######

# import atexit
# import logging
# from printer_server.threading_wrapper import Thread
# from PIL import Image
# import gi
# gi.require_version("Gtk", "3.0")
# from gi.repository import Gtk, Gdk, GLib

# class Screen:
#     """Create and manage a new GTK window."""

#     def __init__(self, resolution, monitor_index=0, log_level=logging.DEBUG):
#         """Initialize a new screen object.

#         resolution: The (width, height) resolution of the screen
#         monitor_index: Index of the monitor where this screen should be displayed.
#         """
#         self.log = logging.getLogger(__name__)
#         self.log.setLevel(log_level)
#         self.image = None
#         self.resolution = resolution

#         self.window = Gtk.Window()
#         self.window.set_default_size(resolution[0], resolution[1])
#         self.window.set_decorated(False)
#         self.window.set_keep_above(True)
#         self.window.fullscreen()

#         self.drawing_area = Gtk.DrawingArea()
#         self.window.add(self.drawing_area)
#         self.drawing_area.connect('draw', self.on_draw)

#         # Position the window based on the monitor index
#         self.monitor_index = monitor_index
#         self.position_window()

#         self.window.show_all()

#     def position_window(self):
#         """Position the window based on the monitor index."""
#         display = Gdk.Display.get_default()
#         monitor = display.get_monitor(self.monitor_index)
#         geometry = monitor.get_geometry()

#         self.window.realize()
#         gdk_window = self.window.get_window()
#         gdk_window.move(geometry.x, geometry.y)

#     def on_draw(self, widget, cr):
#         """Handle the draw event."""
#         if self.image:
#             pixbuf = Gdk.pixbuf_new_from_file_at_scale(self.image, self.resolution[0], self.resolution[1], True)
#             Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
#             cr.paint()

#     def draw(self, img_path):
#         """Draw image in the GTK window."""
#         try:
#             self.image = img_path
#             self.window.queue_draw()
#         except (OSError, FileNotFoundError):
#             self.log.warning("Image not found, drawing white")
#             self.image = None
#             self.window.queue_draw()

#     def clear(self):
#         """Clear the GTK window by drawing a black image."""
#         self.image = None
#         self.window.queue_draw()


# class ScreenThread(Thread):
#     """Create and manage a thread to control the GTK windows."""

#     def __init__(
#         self, config_dict=None, resolutions=((2560, 1600), None), log_level=logging.DEBUG
#     ):
#         self.log = logging.getLogger(__name__)
#         self.log.setLevel(log_level)
#         super().__init__(self.log, name="ScreenThread", daemon=True)
#         self.light_engines = config_dict["light_engines"]
#         self.resolutions = resolutions
#         self.screens = []
#         self.log_level = log_level

#     def run(self):
#         """Create GTK windows and run the main loop."""
#         self.log.info("Starting screen thread")

#         display = Gdk.Display.get_default()
#         n_monitors = display.get_n_monitors()
#         self.log.info("Number of monitors detected: %d", n_monitors)

#         for i, resolution in enumerate(self.resolutions):
#             if resolution is not None and i < n_monitors:
#                 self.screens.append(Screen(resolution, i, self.log_level))

#         atexit.register(self.stop)
#         Gtk.main()

#     def stop(self):
#         """Stop the thread."""
#         if self.screens is not None:
#             self.log.info("Stopping screen thread")
#             for screen in self.screens:
#                 screen.window.close()
#             self.screens = None

#     def draw(self, img_path, screen=0):
#         """Draw an image to the specified screen."""
#         self.log.info("Drawing %s to screen %s", img_path, screen)
#         try:
#             self.screens[screen].draw(img_path)
#         except IndexError:
#             self.log.error("Screen %s does not exist", screen)

#     def clear(self, screen=0):
#         """Clear the specified screen."""
#         self.log.info("Clearing screen %s", screen)
#         try:
#             self.screens[screen].clear()
#         except IndexError:
#             self.log.error("Screen %s does not exist", screen)


####### TK #######

"""Screen module."""
import atexit
import tkinter
import logging
import threading
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
        self.tk_image = None
        self.resolution = resolution
        self.window = tkinter.Toplevel()

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

        # Ensure all geometry management tasks are completed
        self.window.update_idletasks()

        # Set fullscreen
        self.window.attributes('-fullscreen', True)
        self.window.update_idletasks()

    def draw(self, img_path):
        """Draw image in the Tk canvas."""
        try:
            pil_image = Image.open(img_path)
        except (OSError, FileNotFoundError):
            self.log.warning("Image not found, drawing white")
            pil_image = Image.new(mode="L", size=self.resolution, color=255)
        self.tk_image = ImageTk.PhotoImage(pil_image)
        self.canvas.itemconfig(self.canvas_image, image=self.tk_image)
        self.window.update()

    def clear(self):
        """Clear the Tk window by drawing a black image."""
        pil_image = Image.new(mode="L", size=self.resolution, color=0)
        self.tk_image = ImageTk.PhotoImage(pil_image)
        self.canvas.itemconfig(self.canvas_image, image=self.tk_image)
        self.window.update()


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

        root = tkinter.Tk()
        root.withdraw()

        self.screens = []
        self.total_offset = 0
        for resolution in self.resolutions:
            if resolution is not None:
                self.screens.append(Screen(resolution, self.total_offset, self.log_level))
                self.total_offset += resolution[0]
        atexit.register(self.stop)
        tkinter.mainloop()

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



