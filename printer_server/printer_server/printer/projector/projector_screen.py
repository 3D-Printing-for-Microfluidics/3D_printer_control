# `mttkinter` stands for multi-threading tkinter. 
# The `tkinter` in standard library is not technically thread-safe. 
# `mttkinter` wraps it to make it thread-safe. 
from mttkinter import mtTkinter as tkinter
from PIL import Image, ImageTk
import threading


class Screen:
    """The Screen class uses ``tkinter`` as the underlying 
    windowing framework, because ``tkinter`` is part of the 
    Python standard library, and it is platform agnostic. 
    Most importantly, it works. 
    """
    def __init__(self, resolution):
        self.width, self.height = resolution
        self.root = tkinter.Tk()
        # self.root.overrideredirect(True)
        # self.root.overrideredirect(False)
        # self.root.attributes('-fullscreen',True)
        
        # set the size and position of Tk window
        # format: <width>x<height>+xoffset+yoffset
        self.root.geometry('{0}x{1}+0+0'.format(self.width, self.height))
        # hide cursor in the Tk window
        self.root.config(cursor='none')
        self.root.focus_set()
        
        # create a canvas object where we draw images of each 3D print layer
        self.canvas = tkinter.Canvas(self.root,
                                     width=self.width,
                                     height=self.height,
                                     bd=0, # border width
                                     highlightthickness=0, # canvas edge with
                                     relief='ridge')
        # set the canvas position in tk window
        self.canvas.pack()
        # set the canvas background to be black
        self.canvas.configure(background='black')
        # create a canvas image, offset (0, 0), 
        # anchor point NW (northwest), upper left corner 
        self.canvasImage = self.canvas.create_image(0, 0, anchor=tkinter.NW)
        
    def draw(self, fn):
        """Draw image in the Tk canvas.
        :param str fn: image filename
        """
        # open image file as a PIL.Image object
        pilImage = Image.open(fn)
        # Tk canvas only takes `PhotoImage` object
        self.tkImage = ImageTk.PhotoImage(pilImage)
        # change the canvas image to the new image
        # In order to update the Tk window, we still need to call 
        # `root.update`, which is done in the `ScreenThread`. 
        self.canvas.itemconfig(self.canvasImage, image=self.tkImage)
        
    def clear(self):
        """Clear the Tk window by drawing a black image."""
        pilImage = Image.new(mode='1', size=(self.width, self.height))
        self.tkImage = ImageTk.PhotoImage(pilImage)
        self.canvas.itemconfig(self.canvasImage, image=self.tkImage)


class ScreenThread(threading.Thread):
    """A subclass of ``threading.Thread``. The Tk window is 
    created and runs in this thread. 
    
    .. py:attribute:: stopped
    
         a ``threading.Event`` object to set flag to stop thread
    """
    def __init__(self, resolution):
        super().__init__()
        self.resolution = resolution
        self.stopped = threading.Event()
        
    def run(self):
        """Create a Tk window and run it.Instead of the normal 
        ``root.mainloop`` in tkinter, a custom while-loop is 
        implemented such that it can be stopped easily and 
        arbitrary operation can be added, such as guaranteeing 
        the tk window is on top.  
        """
        self.stopped.clear()
        self.screen = Screen(self.resolution)
        while not self.stopped.is_set():
            # set tk window on top
            self.screen.root.wm_attributes("-topmost", 1)
            self.screen.root.update()
            
    def stop(self):
        """Stop the thread"""
        self.stopped.set()
        self.join()



