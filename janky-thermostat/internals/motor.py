import copy
import logging
import queue
import threading
import time

import rgpio
from dual_mc33926 import Motors
from rgpio_ads1115 import ADS1115

from .threadinghelpers import SHUTDOWN_EV

_LOGGER = logging.getLogger(__name__)


def clamp(prev, value, minoffset, maxoffset):
    return max(prev - minoffset, min(value, prev + maxoffset))


def read_position(sensor, previous_position):
    try:
        return sensor.value
    except (rgpio.error, RuntimeError):
        _LOGGER.error("rgpio I2C read failed")
        try:
            return sensor.value
        except (rgpio.error, RuntimeError):
            _LOGGER.error("rgpio I2C read failed again")
            return previous_position


class MoveThread(threading.Thread):
    def __init__(self, motorq: queue.Queue, controllerq: queue.Queue, options):
        super().__init__()
        self.motorq = motorq
        self.controllerq = controllerq
        self.target = -1
        self.moving = 0
        self.offset = 4
        self.settings = copy.deepcopy(options)
        self.POS = ADS1115(
            mode="continuous",
            bus=self.settings["i2c_bus"],
            host=self.settings["rgpio_addr"],
            port=self.settings["rgpio_port"],
        )
        self.motors = Motors(
            host=self.settings["rgpio_addr"],
            port=self.settings["rgpio_port"],
        )
        self.UP = self.settings["updir"]
        self.DOWN = self.UP * -1
        self.STOP = 0

    def run(self):
        try:
            self.motors.enable()
            pos = read_position(self.POS, 0)
            lastmove = time.monotonic()
            reportpositiontime = lastmove
            while not SHUTDOWN_EV.is_set():
                # check if new target
                if not self.motorq.empty():
                    try:
                        packet = self.motorq.get(False)
                        if packet[0] == "P":
                            self.target = packet[1]
                        elif packet[0] == "S":
                            self.settings = packet[1]
                    except queue.Empty:
                        pass
                    if self.target == -2:
                        break

                # current pos
                npos = read_position(self.POS, pos)

                # hectic filtering (lol why am I this jank)
                if self.moving == self.UP:
                    pos = clamp(pos, npos, -(self.offset - 1), self.offset)
                elif self.moving == self.DOWN:
                    pos = clamp(pos, npos, self.offset, -(self.offset - 1))
                else:
                    pos = clamp(pos, npos, 5, 5)

                #print(self.target, round(pos), npos)
                # TODO: Have movement timeout so not just attempting to move forever... first attempt higher speed, then bail
                # seems too hard 'cuz potential changing directions I don't want to deal with it. When I change to actual motor instead of
                # linear actuator this problem will go away 'cuz hopefully stalling won't be an issue.
                if time.monotonic() - reportpositiontime > 2:
                    self.controllerq.put(("AP", pos))
                    reportpositiontime = time.monotonic()

                if self.target != -1:
                    if (self.moving == self.UP or self.moving == self.STOP) and pos < self.target - self.settings["posmargin"]:
                        if self.moving == self.STOP and time.monotonic() - lastmove > 2:
                            if self.moving != self.UP:
                                self.motors.motor2.set_speed(self.UP * self.settings["speed"])
                            self.moving = self.UP
                        if self.moving == self.DOWN:
                            lastmove = time.monotonic()
                    elif (self.moving == self.DOWN or self.moving == self.STOP) and pos > self.target + self.settings["posmargin"]:
                        if self.moving == self.STOP and time.monotonic() - lastmove > 2:
                            if self.moving != self.DOWN:
                                self.motors.motor2.set_speed(self.DOWN * self.settings["speed"])
                            self.moving = self.DOWN
                        if self.moving == self.DOWN:
                            lastmove = time.monotonic()
                    else:  # also stop
                        if self.moving != self.STOP:
                            self.motors.set_speeds(0, 0)
                        self.moving = self.STOP

                if self.moving != 0:
                    SHUTDOWN_EV.wait(0.02)
                else:
                    SHUTDOWN_EV.wait(0.2)
            _LOGGER.info("Exiting motor control loop...")
        finally:
            try:
                self.POS.close()
            except Exception:
                _LOGGER.exception("Failed to close ADS1115")
            try:
                self.motors.close()
            except Exception:
                _LOGGER.exception("Failed to close motor driver")
