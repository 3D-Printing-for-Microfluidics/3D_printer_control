from OpenGL.GL import *
from OpenGL.GLUT import *
from PIL import Image
import sys

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480


class ProjectorScreen:
    def __init__(self):
        self.textureID = 0
        self.textureWidth = 0
        self.textureHeight = 0
        
        self.initGlut()
        self.initGL()
        self.clear()
        self.makeTexture()
        
    def initGlut(self):
        """Initialize glut and s"""
        glutInit(sys.argv)
        # glutInitContextVersion(2, 1)
        glutInitDisplayMode(GLUT_DOUBLE)
        glutInitWindowSize(SCREEN_WIDTH, SCREEN_HEIGHT)
        # glutFullScreen()
        glutCreateWindow(b'3D Printer')
        glutMainLoopEvent()
        
    def initGL(self):
        glViewport(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0., SCREEN_WIDTH, 0., SCREEN_HEIGHT, 1., -1.)
    
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glClearColor(0., 0., 0., 1.)
        glEnable(GL_TEXTURE_2D)
        
    def makeTexture(self):
        
        # free texture
        if self.textureID != 0:
            glDeleteTextures([self.textureID])
            self.textureID = 0
        self.textureWidth = 0
        self.textureHeight = 0
        
        self.textureID = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.textureID)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)
        
    def draw(self, imageName):
        # load image and convert it to bytes
        im = Image.open(imageName)
        pixelBytes = im.tobytes("raw", "L", 0, -1)
        self.textureWidth = im.size[0]
        self.textureHeight = im.size[1]
        
        # clear screen
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        
        # bind our texture for sending and drawing new image
        glBindTexture(GL_TEXTURE_2D, self.textureID)
        
        # send new image bytes to GPU memory
        glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, 
                     self.textureWidth, self.textureHeight, 0, 
                     GL_LUMINANCE, GL_UNSIGNED_BYTE, pixelBytes)
        
        # draw the image
        # (It actually draws a quad with the new image being its texutre)
        glBegin(GL_QUADS)
        glTexCoord2f( 0., 0. ); glVertex2f(                0.,                 0. );
        glTexCoord2f( 1., 0. ); glVertex2f( self.textureWidth,                 0. );
        glTexCoord2f( 1., 1. ); glVertex2f( self.textureWidth, self.textureHeight );
        glTexCoord2f( 0., 1. ); glVertex2f(                0., self.textureHeight );
        glEnd()
        
        # unbind our texture
        glBindTexture(GL_TEXTURE_2D, 0)
        
        # We specify double buffering with `glutInitDisplayMode(GLUT_DOUBLE)`.
        # Double buffering means there are 2 buffers in GPU memory. 
        # GPU draws one frame, while presenting the other one through the 
        # screen. Then, the newly drawn frame is presented, and GPU starts 
        # to draw on the other buffer. 
        # We tell GPU to swap buffers with `glutSwapBuffers()`.
        glutSwapBuffers()
        
    def clear(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glutSwapBuffers()
