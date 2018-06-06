import time


class Solus:
    def __init__(self, serialNum):
        self.serialNum = serialNum
    #     self.is_open = False
    #     self.initialized = False
    #     self.z = 'up'

    def connect(self):
        pass

    def initializeBuildPlatform(self):
        time.sleep(3)

    def goToZeroZ(self):
        time.sleep(3)

    def homing(self):
        time.sleep(3)
        
    def goToFirstLayerHeight(self, *args):
        time.sleep(3)
        
    def resume(self, *args):
        pass
        
    def printCycle(self, *args):
        pass
        
    def pause(self):
        pass
        
    def __del__(self):
        pass
