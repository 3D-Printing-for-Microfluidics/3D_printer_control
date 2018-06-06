from PyQt5 import QtGui, QtWidgets
from stl import mesh
import numpy as np
import os
from ctypes import c_float, c_uint, sizeof
import sys

from printer import printer

GLfloat = c_float
GLuint = c_uint

EPSILON = 0.00001


class OpenGLWidget(QtWidgets.QOpenGLWidget):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.shouldDraw = False
        
    def initializeGL(self):
        self.gl = self.context().versionFunctions()
        self.gl.glEnable(self.gl.GL_DEPTH_TEST)
        self.gl.glClearColor(0.1, 0.1, 0.1, 1.)
        
        self.meshShaderProg = QtGui.QOpenGLShaderProgram()
        self.meshShaderProg.create()
        self.meshShaderProg.addShaderFromSourceFile(
            QtGui.QOpenGLShader.Vertex, 'shaders/mesh.vert')
        self.meshShaderProg.addShaderFromSourceFile(
            QtGui.QOpenGLShader.Fragment, 'shaders/mesh.frag')
        self.meshShaderProg.link()
        
        self.sliceShaderProg = QtGui.QOpenGLShaderProgram()
        self.sliceShaderProg.create()
        self.sliceShaderProg.addShaderFromSourceFile(
            QtGui.QOpenGLShader.Vertex, 'shaders/slice.vert')
        self.sliceShaderProg.addShaderFromSourceFile(
            QtGui.QOpenGLShader.Fragment, 'shaders/slice.frag')
        self.sliceShaderProg.link()
        
        #######################################
        # make VAO for drawing our mesh
        self.VAO = QtGui.QOpenGLVertexArrayObject()
        self.VAO.create()

        self.vertVBO = QtGui.QOpenGLBuffer(QtGui.QOpenGLBuffer.VertexBuffer)
        self.vertVBO.create()
        
        self.normVBO = QtGui.QOpenGLBuffer(QtGui.QOpenGLBuffer.VertexBuffer)
        self.normVBO.create()
        #######################################
        
        self.sliceFbo = QtGui.QOpenGLFramebufferObject(
            printer.width,
            printer.height
        )
        self.sliceFbo.setAttachment(
            QtGui.QOpenGLFramebufferObject.CombinedDepthStencil
        )
        
        maskVert = np.array(
            [[0, 0, 0],
             [printer.width_mm, 0, 0],
             [printer.width_mm, printer.height_mm, 0],

             [0, 0, 0],
             [printer.width_mm, printer.height_mm, 0],
             [0, printer.height_mm, 0]], dtype=GLfloat
        )
        
        ######################################
        # make VAO for drawing mask
        self.maskVAO = QtGui.QOpenGLVertexArrayObject()
        self.maskVAO.create()
        self.maskVAO.bind()

        self.maskVBO = QtGui.QOpenGLBuffer(QtGui.QOpenGLBuffer.VertexBuffer)
        self.maskVBO.create()
        self.maskVBO.bind()
        self.maskVBO.setUsagePattern(QtGui.QOpenGLBuffer.StaticDraw)
        data = maskVert.tostring()
        self.maskVBO.allocate(data, len(data))
        self.gl.glVertexAttribPointer(0, 3, self.gl.GL_FLOAT,
            self.gl.GL_FALSE, 3*sizeof(GLfloat), 0)
        self.gl.glEnableVertexAttribArray(0)

        self.maskVBO.release()
        self.maskVAO.release()
        ######################################
        
    def loadMesh(self, stlFilename):
        # Get information about our mesh
        ourMesh = mesh.Mesh.from_file(stlFilename)
        self.numOfVerts = ourMesh.vectors.shape[0] * 3
        self.bounds = {
            'xmin': np.min(ourMesh.vectors[:,:,0]),
            'xmax': np.max(ourMesh.vectors[:,:,0]),
            'ymin': np.min(ourMesh.vectors[:,:,1]),
            'ymax': np.max(ourMesh.vectors[:,:,1]),
            'zmin': np.min(ourMesh.vectors[:,:,2]),
            'zmax': np.max(ourMesh.vectors[:,:,2])
        }
        self.totalThickness = self.bounds['zmax'] - self.bounds['zmin']
        
        #######################################
        # load mesh data
        self.VAO.bind()
        
        self.vertVBO.bind()
        self.vertVBO.setUsagePattern(QtGui.QOpenGLBuffer.StaticDraw)
        data = ourMesh.vectors.astype(GLfloat).tostring()
        self.vertVBO.allocate(data, len(data))
        self.gl.glVertexAttribPointer(0, 3, self.gl.GL_FLOAT,
            self.gl.GL_FALSE, 3*sizeof(GLfloat), 0)
        self.gl.glEnableVertexAttribArray(0)
        self.vertVBO.release()
        
        self.normVBO.bind()
        self.normVBO.setUsagePattern(QtGui.QOpenGLBuffer.StaticDraw)
        data = np.tile(ourMesh.normals.astype(GLfloat), 3).tostring()
        self.normVBO.allocate(data, len(data))
        self.gl.glVertexAttribPointer(1, 3, self.gl.GL_FLOAT, 
            self.gl.GL_FALSE, 3*sizeof(GLfloat), 0)
        self.gl.glEnableVertexAttribArray(1)
        self.normVBO.release()
        
        self.VAO.release()
        #######################################
        
    def paintGL(self):
        if self.shouldDraw:
            self.draw()
        
    def draw(self):
        self.gl.glViewport(0, 0, self.size().width(), self.size().height())
        self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT | \
                        self.gl.GL_DEPTH_BUFFER_BIT)
        self.meshShaderProg.bind()
        self.VAO.bind()
        
        view = QtGui.QMatrix4x4()
        view.translate(0., 0., 5.)
        view.scale(1., 1., 0.5)
        view.rotate(45., 1., 0., 0.)
        view.rotate(45., 0., 0., 1.)
        view.scale(0.5, 0.5, -0.5)
        self.meshShaderProg.setUniformValue('view', view)
        
        model = QtGui.QMatrix4x4()
        model.translate(-(self.bounds['xmin']+self.bounds['xmax'])/2,
                        -(self.bounds['ymin']+self.bounds['ymax'])/2,
                        -(self.bounds['zmin']+self.bounds['zmax'])/2)
        self.meshShaderProg.setUniformValue('model', model)
        
        lightColor = QtGui.QVector3D(1., 1., 1.)
        lightDir = QtGui.QVector3D(-1., 0., 1.).normalized()
        objectColor = QtGui.QVector3D(0.8, 0.8, 0.8)
        self.meshShaderProg.setUniformValue('lightColor', lightColor)
        self.meshShaderProg.setUniformValue('lightDir', lightDir)
        self.meshShaderProg.setUniformValue('objectColor', objectColor)
        
        self.gl.glDrawArrays(self.gl.GL_TRIANGLES, 0, self.numOfVerts)
        
    def renderSlice(self, sliceHeight, out):
        proj = QtGui.QMatrix4x4()
        proj.ortho(0, printer.width_mm, 
                   0, printer.height_mm, 
                   -self.totalThickness, self.totalThickness)
                   
        model = QtGui.QMatrix4x4()
        model.translate(0, 0, self.totalThickness+EPSILON-sliceHeight)
        
        self.sliceFbo.bind()
        self.gl.glViewport(0, 0, printer.width, printer.height)
        self.gl.glEnable(self.gl.GL_STENCIL_TEST)
        self.gl.glClearColor(0., 0., 0., 1.)
        self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT | self.gl.GL_STENCIL_BUFFER_BIT)
        self.VAO.bind()
        self.sliceShaderProg.bind()

        self.sliceShaderProg.setUniformValue('proj', proj)
        self.sliceShaderProg.setUniformValue('model', model)

        self.gl.glEnable(self.gl.GL_CULL_FACE)
        self.gl.glCullFace(self.gl.GL_FRONT)
        self.gl.glStencilFunc(self.gl.GL_ALWAYS, 0, 0xFF)
        self.gl.glStencilOp(self.gl.GL_KEEP, self.gl.GL_KEEP, self.gl.GL_INCR)
        self.gl.glDrawArrays(self.gl.GL_TRIANGLES, 0, self.numOfVerts)

        self.gl.glCullFace(self.gl.GL_BACK)
        self.gl.glStencilOp(self.gl.GL_KEEP, self.gl.GL_KEEP, self.gl.GL_DECR)
        self.gl.glDrawArrays(self.gl.GL_TRIANGLES, 0, self.numOfVerts)
        self.gl.glDisable(self.gl.GL_CULL_FACE)

        self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT)
        self.maskVAO.bind()
        self.gl.glStencilFunc(self.gl.GL_NOTEQUAL, 0, 0xFF)
        self.gl.glStencilOp(self.gl.GL_KEEP, self.gl.GL_KEEP, self.gl.GL_KEEP)
        self.gl.glDrawArrays(self.gl.GL_TRIANGLES, 0, 6)
        self.gl.glDisable(self.gl.GL_STENCIL_TEST)

        image = self.sliceFbo.toImage()
        # makes a QComboBox for different Image Format,
        # namely Format_Mono, Format_MonoLSB, and Format_Grayscale8
        image = image.convertToFormat(QtGui.QImage.Format_Grayscale8)
        image.save(out)
        self.sliceFbo.release()












