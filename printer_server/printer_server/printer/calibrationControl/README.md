# Notes on writing new drivers for the calibration stages

All drivers should inherit from the CalibrationStage class. This will force you to implement the functions that it 
specifies, which provides a unified interface for the stages to be control through the GUI or the API. 

Do not let your code connect to the stage inside of the __init__() function. Aside from setting up some enviroment variables, 
until the stage needs to be used, the driver code should not be created. We have had problems in the past where initializing 
the driver code causes stages to twitch, and thus bring them out of calibration. 