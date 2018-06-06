.. 3D Printer documentation master file, created by
   sphinx-quickstart on Thu May 10 06:48:30 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to 3D Printer's documentation!
======================================


.. toctree::
   :maxdepth: 3
   :caption: Contents:
   
   project
   information
   print_settings
   printing_thread
   database_schema


TODO
----

#. Fix all tests to work with websockets
#. Alter JSON format and make it programmable
#. Change `archive` to `Print History`
#. Toggle the text in the `Create a job` button
#. Build a print job preparing software
#. Offer download from RPi for the print job preparing software
#. View/download printing history
#. Add re-print feature
#. Figure out **Solus** module with the new motor
#. Add `User` and authentication_
#. Look in to Raspberry Pi

   #. 2560 x 1600 resolution
   #. Show image fullscreen - OpenGL?
   
      * `Raspberry Pi & Python OpenGL Youtube Video
        <https://www.youtube.com/watch?v=lQYlIn1BEfk>`_
   
   #. Tkinter on RPI?
   #. I2C
   #. USB to Arduino
   #. GPIO for Z

#. Benchmark :py:meth:`printer_server.printer.PrintSettings.validate` on RPi
#. Add control panel for **Projector** and **Solus**

.. _authentication: https://flask-socketio.readthedocs.io/en/latest/#authentication

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
