# -*- coding: utf-8 -*-
"""Configuration module. It integrates Solus, Projector into a Printer3D
   and it intergrates all of the calibration stages into a CalibrationConfig.
"""
# possible values: Gen2  | Gen1.1
printer = "Gen1.1"

if printer == "Gen1.1": 
    from printer_server.printer.solus.solus_1_1 import Solus 
else:
    from printer_server.printer.solus.solus import Solus

from printer_server.printer.projector import Projector
from printer_server.printer.print_settings import PrintSettings

from printer_server.printer.calibrationControl.kdc101_stage import KDC101
from printer_server.printer.calibrationControl.stepper_28byj48 import Stepper_28BYJ48

import pickle

#######################################################################################

solusHWID = '1A86:7523'  # specific to each arduino 
projectorResolution = (2560, 1600)

class Printer3D:
    state = 'uninitialized'
    solus = Solus(hwid=solusHWID)
    projector = Projector(projectorResolution)

    def init_app(self, app):
        self.projector.i2c.logger = app.logger

printer3d = Printer3D()

#######################################################################################

calibrationStages =  {"Tip" : Stepper_28BYJ48([14, 15, 18, 4]),
                      "Tilt" : Stepper_28BYJ48([17, 27, 22, 23]),
                    #   "Distance" : KDC101()}
                      "Distance" : Stepper_28BYJ48([24, 25, 10, 9])}

#######################################################################################

# Available Calibration Stages:
# - 28byj48 - RPi GPIO stepper motors
# - kdc101 - thorlabs kinesis stage
calibrationStageTypes = {"Tip": "28byj48", 
                        "Tilt": "28byj48", 
                        # "Distance": "kdc101"}
                        "Distance": "28byj48"}
# names must be the same as the keys in the calibrationStageTypes
stageDisplayOrder = ["Tip", "Tilt", "Distance"]
# Not curreently used
printingMechanismStageTypes = {"z stage": "solusv1", 
                                "x stage": "solusv1"}

# saving/loading pickle info to disk
def saveParamsToDisk(output):
    pickle_out = open(printer + "SavedPositions.pickle", "wb")
    pickle.dump(output, pickle_out)
    pickle_out.close()
    
try:
    pickle_in = open(printer + "SavedPositions.pickle", "rb")
    savedPos = pickle.load(pickle_in)
except:
    savedPos = {}
    for key, _ in calibrationStageTypes.items():
        savedPos[key] = 0.0
    saveParamsToDisk(savedPos)

print("Loaded saved positions: ", savedPos)
