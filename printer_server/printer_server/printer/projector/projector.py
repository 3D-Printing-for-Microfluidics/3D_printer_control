import time

from .projector_screen import ScreenThread
# from .i2cdriver import LightEngineI2C
from .i2cdummy import LightEngineI2C

__all__ = ['Projector']


class Projector:
    
    def connect(self):
        """Create a :py:class:ScreenThread object and run it.
        Also, connect to the I\ :sup:`2`\ C-USB adapter
        """
        self.screenThread = ScreenThread()
        self.screenThread.start()
        self.i2c = LightEngineI2C()
        
    def start(self):
        """Turn on the LED in projector"""
        self.i2c.start()
        
    def stop(self):
        """Turn off the LED in projector"""
        self.i2c.stop()
        
    def setLedAmplitude(self, i):
        """Set the projector LED power level
        :param int i: between 1 and 1000
        """
        self.i2c.setLedAmplitude(i)
        
    @property
    def ledPower(self):
        return self.i2c.ledPower
        
    def projectMulti(self, images, exposureTimes, ledPowers):
        """Project multiple images with its own expoure time and 
        and LED power setting.
        
        :param list images: a list of image filenames
        :param list exposureTimes: a list of exposure times (ms)
        :param list ledPowers: a list of led power settings 
                               (0-1000)
        """
        for im, exposureTime, ledPower in zip(images, exposureTimes, ledPowers):
            self.project(im, exposureTime, ledPower)
            
    def project(self, image, exposureTime, ledPower):
        """Poject a image for a period of t (ms).
        
        TODO: image doesnot have to be 8-bit
        :param image: an 8-bit grayscale image filename
        :param int exposureTime: exposure time (ms)
        :param int ledPower: LED power setting (0-1000)
        """
        max_time = 10000
        n = int(exposureTime // max_time)
        if exposureTime % max_time != 0:
            exposureTime = [max_time] * n + [ exposureTime % max_time ]
        else:
            exposureTime = [max_time] * n
            
        if ledPower != self.ledPower:
            self.setLedAmplitude(ledPower)
            
        for t in exposureTime:
            self.setProjectingTime(t)
            self.screenThread.screen.draw(image)
            time.sleep(0.1)
            self.start()
            time.sleep(0.1 + t * 1e-3)
            self.stop()
            
    def setProjectingTime(self, t):
        '''Set projecting time in millisecond.'''
        repeat = 1
        exptime = int(t * 1e3)
        bitdepth = 7 # 7 means 8 bits
        vsync = 1
        darktime = 0
        bitposition = 0
        sequence = [[exptime, bitdepth, 1, vsync, 
                     darktime, bitposition, 0]]
        self.i2c.parseSendSequence(sequence, repeat)
        
    def clear(self):
        """Clear the projector screen to be black"""
        self.screenThread.screen.clear()
        
    def __del__(self):
        try: 
            self.stop()
            self.screenThread.stop()
            self.i2c.disconnectServer()
        except AttributeError:
            pass
