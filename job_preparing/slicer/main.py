import sys
from PyQt5 import QtGui, QtCore, QtWidgets, uic
import os

from openglwidget import OpenGLWidget, EPSILON
from printer import printer

SCR_WIDTH = 640
SCR_HEIGHT = int(SCR_WIDTH * printer.height / printer.width)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
UI_FILENAME = os.path.join(ROOT_DIR, 'gui', 'mainwindow.ui')
Ui_MainWindow, QMainWindow = uic.loadUiType(UI_FILENAME)


class Window(QMainWindow, Ui_MainWindow):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.dir = ROOT_DIR
        self.connectUi()
        
    def connectUi(self):
        self.toolButtonSelectStl.clicked.connect(self.getStl)
        self.pushButtonStart.clicked.connect(self.startSlicing)
        self.pushButtonSlice.clicked.connect(self.sliceAtCertainHeight)
        
    def getStl(self):
        stlFilename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            'Select STL', 
            self.dir, 
            'STL (*.stl)'
        )
        if stlFilename:
            self.lineEditStl.setText(stlFilename)
            self.pushButtonStart.setEnabled(True)
            self.pushButtonSlice.setEnabled(True)
            try:
                self.openGLWidget.shouldDraw = True
                self.openGLWidget.loadMesh(stlFilename)
                self.openGLWidget.update()
            except:
                QtWidgets.QMessageBox.critical(
                    QtWidgets.QWidget(), 
                    "Error!",
                    "STL file could not be loaded."
                )
                                               
    def startSlicing(self):
        layerThickness = self.doubleSpinBoxLayerThickness.value() * 1e-3 # mm
        sliceSavePath = os.path.join(os.path.dirname(self.lineEditStl.text()), 'slices')
        totalLayerNum = int((self.openGLWidget.totalThickness + EPSILON) // layerThickness)
        
        if not os.path.exists(sliceSavePath):
            os.mkdir(sliceSavePath)
            
        for i in range(1, totalLayerNum+1):
            sliceHeight = i * layerThickness
            self.openGLWidget.renderSlice(
                sliceHeight,
                os.path.join(sliceSavePath, 'out{:04d}.png'.format(i))
            )
                
    def sliceAtCertainHeight(self):
        sliceSavePath = os.path.dirname(self.lineEditStl.text())
        sliceFilename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            'Slice STL', 
            sliceSavePath, 
            'Image (*.png)'
        )
        if sliceFilename:
            self.openGLWidget.renderSlice(
                self.doubleSpinBoxHeight.value(), 
                sliceFilename
            )
        
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            sys.exit()
        event.accept()
        
    def closeEvent(self, event):
        sys.exit()
        event.accept()


def main():
    
    format = QtGui.QSurfaceFormat()
    format.setRenderableType(QtGui.QSurfaceFormat.OpenGL)
    format.setProfile(QtGui.QSurfaceFormat.CoreProfile)
    format.setVersion(4, 1)
    format.setDepthBufferSize(24)
    format.setStencilBufferSize(8)
    QtGui.QSurfaceFormat.setDefaultFormat(format)
    
    app = QtWidgets.QApplication(sys.argv)
    
    window = Window()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()






















