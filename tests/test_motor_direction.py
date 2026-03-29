import importlib
import pathlib
import sys
import types
import unittest
from queue import Queue

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "janky-thermostat"))


class FakeADS1115:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.value = 0

    def close(self):
        return None


class FakeMotorChannel:
    def __init__(self):
        self.speed_calls = []

    def set_speed(self, speed):
        self.speed_calls.append(speed)


class FakeMotors:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.motor1 = FakeMotorChannel()
        self.motor2 = FakeMotorChannel()

    def enable(self):
        return None

    def set_speeds(self, motor1_speed, motor2_speed):
        self.motor1.set_speed(motor1_speed)
        self.motor2.set_speed(motor2_speed)

    def close(self):
        return None


class MoveThreadDirectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._original_modules = {
            "dual_mc33926": sys.modules.get("dual_mc33926"),
            "rgpio_ads1115": sys.modules.get("rgpio_ads1115"),
            "rgpio": sys.modules.get("rgpio"),
        }
        sys.modules["dual_mc33926"] = types.SimpleNamespace(Motors=FakeMotors)
        sys.modules["rgpio_ads1115"] = types.SimpleNamespace(ADS1115=FakeADS1115)
        sys.modules["rgpio"] = types.SimpleNamespace(error=RuntimeError)
        cls.motor_module = importlib.import_module("internals.motor")
        cls.motor_module = importlib.reload(cls.motor_module)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("internals.motor", None)
        for name, original in cls._original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def make_thread(self, updir=1, speed=20):
        return self.motor_module.MoveThread(
            Queue(),
            Queue(),
            {
                "i2c_bus": 0,
                "rgpio_addr": "localhost",
                "rgpio_port": 8889,
                "updir": updir,
                "speed": speed,
                "posmargin": 50,
            },
        )

    def test_command_motor_preserves_speed_magnitude_in_both_directions(self):
        mover = self.make_thread(updir=1, speed=20)

        mover._command_motor(mover.UP)
        mover._command_motor(mover.DOWN)

        self.assertEqual(mover.motors.motor2.speed_calls, [20.0, -20.0])

    def test_refresh_direction_settings_recomputes_reverse_direction(self):
        mover = self.make_thread(updir=1, speed=20)

        mover.settings["updir"] = -1
        mover._refresh_direction_settings()

        self.assertEqual(mover.UP, -1)
        self.assertEqual(mover.DOWN, 1)


if __name__ == "__main__":
    unittest.main()
