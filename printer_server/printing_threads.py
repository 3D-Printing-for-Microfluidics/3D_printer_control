# -*- coding: utf-8 -*-
"""
All the printer operations involve physical movement of certain
parts in the 3D printer. Therefore, it makes sense to throw them
into another thread such that the server stays responsive. This
is achieved by using :py:class:`PrintingThreads`.
"""


import threading
from datetime import datetime
from functools import wraps
import os
from pathlib import Path

from printer_server.extensions import db, socketio
from printer_server.hardware import printer3d
from printer_server.models import PrintRecord
# from printer_server.hardware import calibrationControl


def multithreading(state, text):
    """Make decorators for the printer operation methods.
    The wrapped methods will push the 3D printer state changes
    to clients, and finish the operations in another thread.

    Before::

        def operation(self):
            # code for operation #

    After::

        def operation(self):

            def func(*args, **kwargs):
                # code for operation #
                printer3d.state = 'initialized'
                socketio.emit(printer3d.state, {},
                    namespace='/printing', broadcast=True)

            printer3d.state = 'busy'
            message = {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'text': text
            }
            socketio.emit(printer3d.state, message,
                namespace='/printing', broadcast=True)
            _thread = threading.Thread(target=func,
                                       args=(*args, ),
                                       kwargs={**kwargs, })
            _thread.start()

    :param str state: 3D printer state (Details: :ref:`3d_printer_state_machine`)
    :param str text: printer message for the message box in webpage
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            def func(*args, **kwargs):
                f(*args, **kwargs)
                printer3d.state = state
                socketio.emit(printer3d.state, dict(),
                              namespace='/printing', broadcast=True)

            printer3d.state = 'busy'
            message = {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'text': text
            }
            socketio.emit(printer3d.state, message,
                          namespace='/printing', broadcast=True)
            _thread = threading.Thread(target=func,
                                       args=(*args, ),
                                       kwargs={**kwargs, })
            _thread.start()

        return decorated_function

    return decorator


class PrintingThreads:
    """The PrintingThreads class contains all the 3D printer
    operations. It wraps the ``threading.Thread`` object such that
    a new thread is instantiated every time the 3D printer starts
    an operation. This is because the native Python ``threading.Thread``
    object can only be started once. With a wrapper class, we can
    retain all the useful information under the same namespace.
    This not only allows us to operate the 3D printer with a simple
    method call but also enables us to implement resuming printing
    very easily.

    .. py:attribute:: jsonDir

        the image path

    .. py:attribute:: printingStopped

        a ``threading.Event`` object to set flag to stop printing

    .. py:attribute:: printingPaused

        a ``threading.Event`` object to set flag to pause printing

    .. py:attribute:: pausedLayer

        the layer where the print is paused. If ``pausedLayer``
        is ``i``, it will start printing layer ``i`` after resume.

    """
    def __init__(self):
        self.printer3d = printer3d
        self.galil = printer3d.galil
        self.projector = printer3d.projector
        self.kdc = printer3d.kdc
        self.tiptilt = printer3d.tiptilt
        self.printSettings = None
        self.jsonDir = None
        self.printingStopped = threading.Event()
        self.printingPaused = threading.Event()
        self.pausedLayer = 1
        self._thread = None                         # will be initialized later on start
        self.logs_path = Path.cwd() / 'logs'
        self.logs_path_directory_for_this_run = None   # initialized later

    def calculateThickness(self, start, end):
        """ Helper funtion to calculate the layer thickness in um
        """
        return self.galil.cntsToMm(abs(end - start)*1000)

    @multithreading('initialized', 'Initialize')
    def initialize(self):
        """Establish Ethernet connection with Galil controler,
        and find zero in Z axis for build platform.
        """
        self.tiptilt.connect()
        self.kdc.initialize()
        self.projector.connect()
        self.galil.connect()
        self.galil.motorOn()
        self.galil.home()
        self.galil.goToZmax()

        # self.galil.openEncoderFile('encoder_initialization_write_file.txt')
        # self.galil.closeEncoderFile()


    @multithreading('planarizing', 'Planarization Step 1')
    def planarizationStep1(self):
        """Planarization Step 1 -- Lower the build platform to
        zero in Z for planarization.
        """
        # print("Planarization Step 1")
        # self.galil.openEncoderFile('encoder_planarization_write_file.txt')
        self.galil.goToZmin()
        # self.galil.closeEncoderFile()

    @multithreading('planarized', 'Planarization Step 2')
    def planarizationStep2(self):
        """Planarization Step 2 -- Make sure the build platform
        is flat on the teflon film. Then tighten the screws and
        bring the build platform to home position in Z.
        """
        # self.galil.goToZmax()
        # self.galil.goToPlanarizationPullOff()

    @multithreading('paused', 'Pause Printing')
    def pause(self):
        """Pause the printing process. It is implemented with a
        ``threading.Event`` object, :py:attr:`printingPaused`.
        The :py:meth:`printingPaused.is_set()` is only checked at
        the beginning of every layer. If ``True``, the printing
        will be paused. If the operations of a layer have started,
        the 3D printer will finish that layer first. After being
        paused, the 3D printer can resume and continue finishing
        the print job.
        """
        self.printingPaused.set()
        self._thread.join()

    @multithreading('stopped', 'Stop Printing')
    def stop(self):
        """Stop the printing process. It works basically the same
        as :py:meth:`puase`, except the 3D printer can not resume
        and finish the previous print job.
        """
        self.printingStopped.set()
        self._thread.join()
        # self.galil.closeEncoderFile()
        # self.galil.closeLoadCellFile()

    def start(self):
        """This method starts a new print.

        If printer is planarized, this method starts printing from
        layer 1 in a new thread. When printing is completed, paused,
        or stopped, the thread ends gracefully.
        """
        self.printer3d.state = 'printing'
        message = {
            'percent': 0,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'text': 'Start Printing'
        }
        socketio.emit(self.printer3d.state, message, namespace='/printing', broadcast=True)

        app = db.get_app()
        self._thread = threading.Thread(target=self.startPrinting, args=(1, app))
        self._thread.start()

    def resume(self):
        """This method resumes a paused print.

        If printing is paused, this method starts printing from
        :py:attr:`pausedLayer` in a new thread. When printing is
        completed, paused, or stopped, the thread ends gracefully.
        """
        self.printer3d.state = 'printing'
        message = {
            'percent': int(100*(self.pausedLayer-1)/self.printSettings.totalLayerNum),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'text': 'Resume Printing'
        }
        socketio.emit(self.printer3d.state, message, namespace='/printing', broadcast=True)

        app = db.get_app()
        self._thread = threading.Thread(target=self.startPrinting, args=(self.pausedLayer, app))
        self._thread.start()

    def startPrinting(self, startingLayer, app):
        """The ``startPrinting`` method implements the printing
        process.

        .. note::
            This method should **NEVER** be called from the main
            thread. Otherwise, it will block the main thread until
            it is done, and cannot be interrupted.

        .. describe:: Printing process

        #. It starts with initializing parameters.
        #. Then the build platform move to the starting height.
        #. The layers will be iterated from the starting layer to
           the last.

            #. Every layer starts with checking whether printing
               is stopped or paused.
            #. If not, it goes through the mechanical operations
               in Galil first, and then exposes the layer with
               all the images.

        #. If the printing is stopped, paused, or completed, it
           exits the for-loop, cleans up, and ends gracefully.

            #. If printing is paused, the current layer number
               will be saved to :py:attr:`pausedLayer`, and the
               build platform will move up 30 mm and wait for
               further instruction.
            #. If printing is stopped, the build platform will
               move up to home position.

        :param int startingLayer: the layer to start printing
        :param app: the current flask ``app`` object. We have to
                    get ``app`` in the main thread, and pass it
                    to the working thread. The reason that we need
                    ``app`` is that in order to interact with
                    database, we have to be under ``app_context``.
                    See http://flask-sqlalchemy.pocoo.org/contexts/.
        """
        # Initialize parameters
        self.printingStopped.clear()
        self.printingPaused.clear()

        # Create log
        date_and_time = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
        self.logs_path_directory_for_this_run = self.logs_path / date_and_time
        self.logs_path_directory_for_this_run.mkdir()
        encoder_print_file_name = str(self.logs_path_directory_for_this_run / 'encoder_print_file.txt')
        # load_cell_file_name = self.logs_path_directory_for_this_run / 'load_cell_print_file.txt'

        # Move build platform to the starting position
        if startingLayer == 1:
            start, end = self.galil.printCycle(self.printSettings.getLayerThicknessMm(1), self.printSettings.getCommandChain(1))
            with open(encoder_print_file_name, "a") as f:
                f.write("Layer {}: start {}, end {}, thickness {}\n".format(1, start, end, self.calculateThickness(start, end)))
        else:
            self.galil.resume(self.printSettings.getLayerThicknessMm(startingLayer))

        # Iterate from the startingLayer to the last
        totalLayerNum = self.printSettings.totalLayerNum
        for i in range(startingLayer, totalLayerNum+1):
            if self.printingStopped.is_set() or self.printingPaused.is_set():
                self.pausedLayer = i # layer i has not been exposed
                break

            # self.galil.encoder_print_file.write("Layer %d \r\n" %(i))
            if i != startingLayer:
                start, end = self.galil.printCycle(self.printSettings.getLayerThicknessMm(i), self.printSettings.getCommandChain(i))
                with open(encoder_print_file_name, "a") as f:
                    f.write("Layer {}: start {}, end {}, thickness {}\n".format(i, start, end, self.calculateThickness(start, end)))

            images = [os.path.join(self.jsonDir, im) for im in self.printSettings.getImages(i)]

            self.projector.projectMulti(images, self.printSettings.getExposureTimeMs(i), self.printSettings.getLedPowers(i))

            socketio.emit('print progress',
                          {'percent': int(100*i/totalLayerNum),
                           'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                           'text': 'Layer {}'.format(i)},
                          namespace='/printing', broadcase=True)

        # Clean up
        # self.galil.stopLoadCell()
        self.projector.stop_sequencer()
        self.projector.screenThread.screen.clear()
        if self.printingPaused.is_set():
            self.galil.pause()
        else:
            self.galil.goToZmax()

            # save the end time to database
            with app.app_context():
                latestPrintRecord = PrintRecord.query.\
                    order_by(PrintRecord.id.desc()).first()
                latestPrintRecord.end_time = datetime.now()
                if self.printingStopped.is_set():
                    latestPrintRecord.completed = False
                latestPrintRecord.save()

            if not self.printingStopped.is_set() and not self.printingPaused.is_set():
                self.printer3d.state = 'completed'
                message = {
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'text': 'Printing Compeleted'
                }
                socketio.emit(self.printer3d.state, message,
                              namespace='/printing', broadcast=True)
        # self.galil.closeEncoderFile()
        # self.galil.closeLoadCellFile()

    @property
    def isBusy(self):
        """boolean -- whether the printer is printing"""
        return self._thread.isAlive()
