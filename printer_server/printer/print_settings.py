# -*- coding: utf-8 -*-
"""
Standard for Print Job
======================

JSON File
---------

Boilerplate
^^^^^^^^^^^

The JSON file contains all the information needed for a print
besides the images. Here is a most simplified version, namely,
all the entries are necessary. ::

    {
      "Header": {
        "Schema version": "0.1",
        "Image directory": "slices"
      },
      "Default settings": {
        "Light engine power setting": 100,
        "Layer exposure time (ms)": 400,
        "Layer thickness (um)": 10,
        "Number of duplications": 1,
        "Galil command chain": [
          "WAIT 0.1",
          "UP 1 SPEED 300 ACC 50",
          "WAIT 1.5",
          "UP 2 SPEED 400 ACC 50",
          "DOWN 3 SPEED 400 ACC 50",
          "WAIT 1.5"
        ]
      },
      "Layers": [
        {
          "Images": [
            "0000.png"
          ]
        }
      ]
    }

**Explanation of all entries**

#. Header

    #. Schema version - for backward compatibility
    #. Image directory - relative the directory of JSON file

#. Default settings - Default values

    #. Light engine power setting - an integer between 0 and 1000
    #. Layer exposure time (ms)
    #. Layer thickness (um)
    #. Number of duplications - If a number of consective layers
       share the same images and parameters, we can set
       ``Number of duplications`` to reduce json file footprint.
    #. Galil command chain - command chain
       to tell Galil controller how to move BP.
       (Details: :ref:`galil_command_chain`)

#. Layers - a list of layer settings. Each item in the list
   is corresponding to multiple layers, when
   ``Number of duplications`` is greater than 1.


.. _galil_command_chain:

Galil command chain
^^^^^^^^^^^^^^^^^^^

The Galil movement starts from right after exposure, and ends
right before another exposure. Here, a new API for moving the
build platform is introduced. With the new API, any
arbitrary combination of movements can be implemented by
chaining a list of commands.

**Command format examples**

* Wait (WAIT)

    * Wait 1.5 seconds
        * ``WAIT 1.5``

* Build Platform (BP)

    * Move build platform up 1 mm at 25 mm/sec
        * ``UP 1 SPEED 20``

    * Move build platform down 1.5 mm at 25 mm/sec
        * ``DOWN 1.5 SPEED 25``

**Rules**

We can almost chain commands however we want to, but there are
still some rules.

* ``BP`` rules

    #. Speed must be positive integer, units are mm/sec.
    #. Acceleration must be positive integer, units are mm/sec^2.
    #. The total distance of ``UP`` should be the same as
       ``DOWN``.

.. Note::
    Because ``UP`` distance is equal to ``DOWN`` distance,
    there is not a new layer of resin between the printed part
    and the build surface. This is taken care of in the
    Galil.printCycle method, which automatically reduces the
    last ``DOWN`` distance by the layer thickness.


JSON with extra information and customized layer settings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Besides basic information, we can add a detailed description under
other entries. This extra information does not affect the print
in any way. Example ::

    {
      "Design": {
        "Purpose": "String with short statement about design's
                    purpose.",
        "Description": "String containing description of design
                        to be printed with this JSON file. Could
                        be multi-line by using '\\n' to separate
                        lines.",
        "Resin": "Resin that this design is intended to be used
                  with. Example: PEGDA with 2% NPS and 1%
                  Irgacure 819.",
        "3D printer": "3D printer that this design is intended
                       to be printed on.",
        "Design file": "<filename> (OpenSCAD or other 3D CAD file
                        containing design)",
        "STL file": "<filename>",
        "Slicer": "Specify which slicer was used to create png
                   images from STL file.",
        "Date": "Date file was sliced."
      },
      "Header": {
        "Comment": "This section contains information about the
                    schema and the directory where to find images,
                    which is specified relative to the directory
                    in which this json file resides. If the json
                    file is in the same directory as the png
                    images, this would be `.`",
        "Schema version": "0.1",
        "Image directory": "slices"
      }
      "Default settings": {
        "Comment": "Default settings for the Printer. Unless
                    otherwise defined in the layer, these are
                    the values that are to be used for each
                    layer.",
        "Light engine power setting": 100,
        "Layer exposure time (ms)": 400,
        "Layer thickness (um)": 10,
        "Number of duplications": 1,
        "Galil command chain": [
          "WAIT 0.1",
          "UP 1 SPEED 20 ACC 25",
          "WAIT 1.5",
          "UP 2 SPEED 20 ACC 25",
          "DOWN 3 SPEED 20 ACC 25",
          "WAIT 1.5"
        ]
      },
      "Layers": [
        {
          "Images": [
            "0000.png"
          ],
          "Layer exposure time (ms)": [
            20000
          ],
          "Layer thickness (um)": 20,
          "Comment": "This layer has a custom exposure time and
                      layer thickness."
        },
        {
          "Images": [
            "0000.png"
          ],
          "Layer exposure time (ms)": [
            10000
          ],
          "Number of duplications": 2,
          "Comment": "This layer is duplicated twice, which means
                      it is actually for layer 2 and 3."
        },
        {
          "Images": [
            "0000.png"
          ],
          "Layer exposure time (ms)": [
            5000
          ],
          "Light engine power setting": [
            200
          ],
          "Comment": "This layer has custom light engine power
                      setting."
        },
        {
          "Images": [
            "0001.png",
            "0001a.png"
          ],
          "Comment": "This layer exposes 2 images using default
                      settings."
        },
        {
          "Images": [
            "0002.png",
            "0002a.png"
          ],
          "Layer exposure time (ms)": [
            400,
            200
          ],
          "Comment": "This layer exposes 2 images with different
                      exposure times."
        },
        {
          "Images": [
            "0003.png",
            "0003a.png"
          ],
          "Light engine power setting": [
            200,
            400,
          ],
          "Comment": "This layer exposes 2 images with different
                      light engine power settings."
        },
        {
          "Images": [
            "0004.png",
            "0004a.png"
          ],
          "Layer exposure time (ms)": [
            400,
            200
          ],
          "Light engine power setting": [
            200,
            400,
          ],
          "Comment": "This layer exposes 2 images with different
                      exposure times and light engine power
                      settings."
        },
        {
          "Images": [
            "0005.png"
          ],
          "Galil command chain": [
            "WAIT 0.1",
            "UP 3 SPEED 300",
            "WAIT 1.5",
            "DOWN 3 SPEED 400",
            "WAIT 1.5"
          ],
          "Comment": "The layer has its own command chain to
                      control the Galil controller."
        },
        {
          "Images": [
            "0006.png"
          ],
          "Comment": "A normal layer"
        }
      ]
    }

We can customize any layer by override the default values. In
the above JSON file, the first list item in ``Layers`` contains
``Layer exposure time (ms)`` and ``Layer thickness (um)``,
which means the first layer will have exposure time of 20000 ms
and layer thickness of 20 um. Note that a number of consective
layers can share one list item by making
``Number of duplications`` greater than 1. The purpose is to
reduce repetitive information. For instance, in the second list
item above, ``Number of duplications`` is 2, which is mapped to
layer 2 and 3.

Also, a layer can expose however many images. For every image,
you can set exposure times and light engine power settings,
repectively. If so, every image must have an exposure time. Same
for light engine power setting.


Format of A Print Job
---------------------

To submit a print job to the 3D printer, a ZIP file is the only
format the 3D printer accepts. This ZIP file should contain only
one JSON file, named ``print_settings.json``, and all the images
that will be used for this print job. The file structure in the
ZIP file should be as following ::

    .
    ├── print_settings.json
    └── slices
        ├── 0000.png
        ├── 0001.png
        ├── 0002.png
        └── 0003.png
            .
            .
            .

The name of the JSON file must be ``print_settings.json``, and
the names of the images and image folder name need to match what
is specified in the json file.

.. Note::
    After the ZIP file is extracted, the JSON file directory will
    be used as the root directory. Image directory is relative
    to the root directory.

"""


import re
import json
import zipfile
import os
import shutil


class PrintSettings:
    """The PrintSettings class wraps the dictionary loaded from
    the JSON file. It also provides some utility functions,
    which makes it easy to get parameter values from a nested
    dictionary.

    :param dict settings: a dictionary of print settings.
    """

    waitRegex = re.compile(r'WAIT (-?\d+(\.\d+)?)')
    moveRegex = re.compile(r'^(UP|DOWN) (-?\d+(\.\d+)?) SPEED (-?\d+(\.\d+)?) ACC (-?\d+(\.\d+)?)')

    def __init__(self, settings):
        self.__settings = settings

        # Puts the number of duplications for each image into a
        # list
        self.__listOfDuplication = list()
        for layer in self.__settings['Layers']:
            try:
                numOfDup = layer['Number of duplications']
            except KeyError:
                numOfDup = self.__settings['Default settings']\
                                         ['Number of duplications']
            self.__listOfDuplication.append(numOfDup)

        # Creates another list where each value is corresponding
        # to only one layer such that we can quickly look up
        # layer parameters.
        self.__mapOfLayers = list()
        for i, dup in enumerate(self.__listOfDuplication):
            self.__mapOfLayers += [i] * dup

    @classmethod
    def fromFile(cls, filename):
        """Create a PrintSettings object from a json file.

        :param str filename: JSON file that has the print settings
        """
        with open(filename, 'r') as f:
            settings = json.load(f)
        return cls(settings)

    @property
    def totalLayerNum(self):
        """
        :returns: the total layer number of a print job
        :rtype: int
        """
        return sum(self.__listOfDuplication)

    def __getLayerParam(self, layerNum, paramName):
        """Utility function to get a specific parameter for
        a given layer.

        :param int layerNum: the index of a layer, starting with 1
        :param str paramName: parameter name
        :returns: a layer parameter value
        """
        try:
            i = self.__mapOfLayers[layerNum-1]
            return self.__settings['Layers'][i][paramName]
        except KeyError: # TODO: This key error gets caught when key doesn't exist OR when it is wrong. That means it
                         # is possible for a user to think they are putting in good information but the software will
                         # ignore it and keep running without notification. Validation should be more robust to
                         # prevent this
            return self.__settings['Default settings'][paramName]

    def getLayerThicknessMm(self, layerNum):
        """
        :param int layerNum: the index of a layer, starting with 1
        :returns: the layer thickness for the specified layer in
                  millimeters
        :rtype: float
        """
        return self.__getLayerParam(
            layerNum,
            'Layer thickness (um)'
        ) * 1e-3

    def getCommandChain(self, layerNum):
        """
        :param int layerNum: the index of a layer, starting with 1
        :returns: a list of Galil commands
        :rtype: list
        """
        return self.__getLayerParam(layerNum, 'command chain')

    def getImages(self, layerNum):
        """
        :param int layerNum: the index of a layer, starting with 1
        :returns: a list of image names with the full directory
        :rtype: list
        """
        return [
            os.path.join(
                self.__settings['Header']['Image directory'],
                im
            ) for im in self.__getLayerParam(layerNum, 'Images')
        ]

    def getExposureTimeMs(self, layerNum):
        """
        :param int layerNum: the index of a layer, starting with 1
        :returns: a list of exposure time in milliseconds
        :rtype: list
        """
        temp = self.__getLayerParam(layerNum, 'Layer exposure time (ms)')
        if not isinstance(temp, list):
            temp = [temp] * len(self.__getLayerParam(layerNum, 'Images'))
        return temp

    def getLedPowers(self, layerNum):
        """
        :param int layerNum: the index of a layer, starting with 1
        :returns: a list of light engine power settings
        :rtype: list
        """
        temp = self.__getLayerParam(layerNum, 'Light engine power setting')
        if not isinstance(temp, list):
            temp = [temp] * len(self.__getLayerParam(layerNum, 'Images'))
        return temp

    @classmethod
    def validate(cls, filename, path):

        """This method validates the (.zip) file of a print job.

        What does it check?

        #. The ZIP file is not corrupted.
        #. There is only one JSON file named ``print_settings.json``.
        #. The JSON file can be successfully loaded, and it
           contains all the necessary entries.
        #. The values of these entries are the correct type.
        #. The images used actually exist.
        #. The Galil command chain syntax is correct.

        :param str filename: a zip file with directory tree as
                             following
        :param str path: a directory to extract all files, which
                         should be ``os.path.join(Config.UPLOAD_FOLDER, 'tmp')``.
                         Extracted files will be removed afterwards.
        :returns: whether it passes validation or not
        :rtype: boolean
        """
        try:
            with zipfile.ZipFile(filename, 'r') as zf:
                files = [f for f in zf.namelist() if not f.startswith('__MACOSX')]
                jsonFiles = [f for f in files if f.endswith('print_settings.json')]
                assert len(jsonFiles) == 1
                jsonFile = jsonFiles[0]
                zf.extract(jsonFile, path=path)

            settings = cls.fromFile(os.path.join(path, jsonFile))
            shutil.rmtree(path)
            jsonDir = os.path.dirname(jsonFile)

            settings.checkDefault()
            settings.checkLayers(jsonDir, files)
        except json.decoder.JSONDecodeError:
            shutil.rmtree(path)
            return False
        except:
            print("other validation error")
            return False

        return True

    def checkDefault(self):
        assert isinstance(self.__settings['Default settings']['Light engine power setting'], int)
        assert isinstance(self.__settings['Default settings']['Layer exposure time (ms)'], int)
        float(self.__settings['Default settings']['Layer thickness (um)'])
        assert isinstance(self.__settings['Default settings']['Number of duplications'], int)
        self.checkGalilCommandChain(self.__settings['Default settings']['command chain'])

    def checkLayers(self, jsonDir, files):
        for layer in self.__settings['Layers']:
            for image in layer['Images']:
                assert os.path.join(jsonDir, self.__settings['Header']['Image directory'], image) in files

            try:
                # Check to make sure there is the same number of images and LED powers
                assert len(layer['Light engine power setting']) == len(layer['Images'])
                for i in layer['Light engine power setting']:
                    assert isinstance(i, int)
            except KeyError:
                pass

            try:
                # Check to make sure there is the same number of images and exposure times
                assert len(layer['Layer exposure time (ms)']) == len(layer['Images'])
                for i in layer['Layer exposure time (ms)']:
                    assert isinstance(i, int)
            except KeyError:
                pass

            try:
                float(layer['Layer thickness (um)'])
            except KeyError:
                pass

            try:
                assert isinstance(layer['Number of duplications'], int)
            except KeyError:
                pass

            try:
                self.checkGalilCommandChain(layer['command chain'])
            except KeyError:
                pass

    def checkGalilCommandChain(self, commandChain):
        totalDistance = 0

        for command in commandChain:
            m1 = self.waitRegex.fullmatch(command)
            m2 = self.moveRegex.fullmatch(command)

            if m1:                                              # is a wait command
                # wait_seconds = m1.group(2)
                continue
            elif m2:                                            # is a move command
                direction = m2.group(1)
                distance = m2.group(2)
                # speed = m2.group(4)
                # acceleration = m2.group(6)
                sign = 1 if direction == 'UP' else -1           # convert direction to a sign
                totalDistance += sign * float(distance)         # sum all movements
            else:                                               # if command didn't match either regex
                print("Bad command, must be UP, DOWN, or WAIT")
                raise AssertionError

        if totalDistance != 0:                                  # if the total distance on this layer isn't 0
            print("Upward and downward movements don't add to 0")
            raise AssertionError
