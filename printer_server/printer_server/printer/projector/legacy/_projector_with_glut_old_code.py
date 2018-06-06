from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import sys, time
import numpy as np
from PIL import Image
from .i2cdriver import LightEngineI2C

__all__ = ['Projector']

class Projector:
    '''Projector have the functionality of taking a image and projecting it for a given period.'''
    def __init__(self):
        self.i2c = LightEngineI2C()
        self.w, self.h = 2560, 1600
        self.pxArr = np.zeros((self.h, self.w), dtype=np.uint8)
        self.window = None
        self.glutWindow = None
        
    def project(self, file, t, waitBeforeExposure, waitAfterExposure):
         '''Poject a image for a period of t (ms).'''
        self.setProjectingTime(t)
        self.updateScreen(file)
        self.draw(image)
        time.sleep(0.1 + waitBeforeExposure * 1e-3)
        self.i2c.start()
        time.sleep(0.1 + t * 1e-3 + waitAfterExposure * 1e-3)
        self.i2c.stop()
        
    def updateScreen(self, file):
        img = Image.open(file)
        self.pxArr = np.array(img)
        self.draw()
        
    def setProjectingTime(self, t):
        '''Set projecting time in millisecond.'''
        repeat = 1
        exptime = int(t * 1e3)
        bitdepth = 7 # 7 means 8 bits
        vsync = 1
        darktime = 0
        bitposition = 0
        sequence = np.array([[exptime, bitdepth, 1, vsync, darktime, bitposition, 0]], dtype=int)
        self.i2c.parseSendSequence(sequence, repeat)
        
    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glDrawPixels(self.w, self.h, GL_LUMINANCE, GL_UNSIGNED_BYTE, np.ascontiguousarray(self.pxArr).data)
        glutSwapBuffers()
        
     def display(self):
        '''Initializes the display and displays the given image. 
        '''
        glutInit(sys.argv)
        glutInitDisplayMode(GLUT_DOUBLE | GLUT_LUMINANCE)
        glutInitWindowSize(self.w, self.h)
        glutInitWindowPosition(1680*2,0)
        self.glutWindow = glutCreateWindow(b"Draw Pixels using Python")
        glutFullScreen()
        glutDisplayFunc(self.draw)
        glutSetCursor(GLUT_CURSOR_NONE) # hide cursor when it's in the window
        glClearColor( 0., 0., 0., 1.)
        glutMainLoopEvent()
        
    def destroyGlutWindow(self):
        glutDestroyWindow(self.glutWindow)
        self.glutWindow = None
        
     def __del__(self):
         self.i2c.stop()
         self.i2c.disconnectServer()