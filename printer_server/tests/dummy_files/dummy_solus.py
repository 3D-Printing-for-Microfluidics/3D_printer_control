# -*- coding: utf-8 -*-
"""Dummy Solus module, used for development."""
import time
import re


class Solus:
    def __init__(self, hwid):
        self.hwid = hwid
        self.regex = re.compile(r'^(BP|QW) (UP|DOWN) (-?\d+(\.\d+)?) SPEED (\d+)')

    def connect(self):
        print("Solus: connect()")

    def initialize(self):
        print("Solus: initialize()")
        time.sleep(1)

    def goToZmin(self):
        print("Solus: goToZmin()")
        time.sleep(1)

    def goToZmax(self):
        print("Solus: goToZmax()")
        time.sleep(1)

    def goToFirstLayerHeight(self, *args):
        print("Solus: goToFirstLayerHeight()")
        time.sleep(1)

    def resume(self, *args):
        print("Solus: resume()")

    def printCycle(self, layerThicknessMm, commandChain):
        # TODO: explain the code here
        for i in range(len(commandChain)-1, -1, -1):
            if commandChain[i].startswith('BP'):
                a = i
                break
            if i == 0:
                a = -1

        if a == -1:
            commandChain.append('BP UP {:.4f} SPEED 400'.format(layerThicknessMm))
        else:
            lastBpCommand = commandChain[a].split()
            distance = float(lastBpCommand[2])
            speed = lastBpCommand[4]
            if lastBpCommand[1] is 'UP':
                newCommand = 'BP UP {:.4f} SPEED {}'.format(distance+layerThicknessMm, speed)
            else:
                newCommand = 'BP DOWN {:.4f} SPEED {}'.format(distance-layerThicknessMm, speed)
            commandChain[a] = newCommand

        for command in commandChain:
            self.execute(command)

    def execute(self, command):
        # Example: `WAIT 1.5` => `time.sleep(1.5)`
        if command.startswith('WAIT'):
            time.sleep(float(command.split()[1]))
            return

        m = self.regex.fullmatch(command)
        if m:
            direction = m.group(2)
            distance = float(m.group(3))
            speed = int(m.group(5))
            if m.group(1) == 'BP':
                self.moveZ(direction, distance, speed)
            elif m.group(1) == 'QW':
                self.moveX(direction, distance, speed)

    def moveX(self, direction, distance, speed):
        """Move quartz window up/down a certain distance at a
        given speed.

        :param str direction: can only be 'UP' or 'DOWN'
        :param distance: distance in millimeters.
        :param speed: Always treated as positive. The unit is mm/min.
        """
        if direction == 'UP':
            distance = -distance
        print('Solus: G1 X{:.4f} F{:d}'.format(distance, abs(speed)))

    def moveZ(self, direction, distance, speed):
        """Move build platform up/down a certain distance at a
        given speed.

        :param str direction: can only be 'UP' or 'DOWN'
        :param distance: distance in millimeters.
        :param speed: Always treated as positive. The unit is mm/min.
        """
        if direction == 'UP':
            distance = -distance
        print('Solus: G1 Z{:.4f} F{:d}'.format(distance, abs(speed)))




    def pause(self):
        print("Solus: pause()")

    def __del__(self):
        pass
