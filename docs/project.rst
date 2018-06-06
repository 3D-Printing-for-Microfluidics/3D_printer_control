***************************
Introduction to the Project
***************************

The purpose of this project is to build a software for our custom DLP-based 
stereolithography 3D printer. 


Hardware Architecture
---------------------

The idea is to use a Raspberry Pi (RPi) or a mini PC as a server to control 
all the hardware, while it also provides a web interface for users at the 
same time. A user can visit the server on another computer through a browser. 
In the browser, they can submit print jobs and control the 3D printer. 

The architecture of the 3D printer looks like:

.. image:: images/printer\ server\ software\ architechture.png
   :scale: 40 %


Software Architecture
---------------------

The heart of the software is Flask, a Python web framework. It handles requests 
from client, gives feedback, and control send commands to operate 3D printer. 


.. _3d_printer_state_machine:

3D Printer State Machine
------------------------

The 3D printer works as a state machine. 

.. image:: images/3d\ printer\ state\ machine.png
   :scale: 40 %

#. When the server is started, we have to initialize it first. 
#. After being initialized, the build platform needs to be planarized. 
   The planarization consists of 2 steps. 

   #. Step 1 is to lower the build platform to zero position in Z.
   #. Step 2 is to make sure the build platform is planarized, and return 
      it to home position in Z. 

#. Now the 3D printer is ready for a print. Select a uploaded print job 
   (details at :py:mod:`printer_server.printer.print_settings`), and start. 
#. The printing process can be paused, resumed, and stopped. Once it is 
   stopped or completed, the build platform needs to be taken off for 
   post-processing the print. 


Real-time update
----------------

The 3D printer server software depends heavily on websocket. Websocket is a 
bidrectional communication protocol between server and client, which allows 
server to push updates to clients in real time. (More info: :ref:`websockets`)

After 3D printer webpage is opened up, a websocket is automatically established 
between client and server. The server updates the client webpage with any changes 
of the 3D printer, namely printer states and operations. Also, the client can 
send commands to control 3D printer via websocket. Moreover, websocket allows 
multiple clients to connect with server, even multiple sockets from one client. 
In either case, websockt can push updates to all clients such that all the 3D 
printer webpages are synchronized. 