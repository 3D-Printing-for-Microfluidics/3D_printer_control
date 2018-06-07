from printer_server.printer.solus import Solus
from printer_server.printer.projector import Projector
from printer_server.printer.print_settings import PrintSettings


solusSerialNum = '95530343534351102222'
projectorResolution = (640, 400)


class Printer3D:
    state = 'uninitialized'
    solus = Solus(serialNum=solusSerialNum)
    projector = Projector(projectorResolution)


printer3d = Printer3D()

