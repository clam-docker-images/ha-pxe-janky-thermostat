import importlib
import pathlib
import sys
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "janky-thermostat"))


class FakePahoClient:
    def __init__(self, client_id):
        self.client_id = client_id

    def publish(self, topic, payload=None, qos=0, retain=False):
        return None

    def subscribe(self, topic, qos=0):
        return None

    def unsubscribe(self, topic):
        return None

    def message_callback_add(self, topic, callback):
        return None

    def message_callback_remove(self, topic):
        return None


class FakeSHT4x:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.measurements = (20.0, 50.0)

    def close(self):
        return None


class FakePID:
    def __init__(self, kp, ki, kd, setpoint, output_limits, auto_mode):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.output_limits = output_limits
        self.auto_mode = auto_mode
        self.components = (0.0, 0.0, 0.0)

    def __call__(self, temperature):
        return None

    @property
    def tunings(self):
        return self.kp, self.ki, self.kd

    @tunings.setter
    def tunings(self, value):
        self.kp, self.ki, self.kd = value


class FakeStateEntity:
    def __init__(self, value=None):
        self.value = value
        self.force_publish_calls = 0

    def forcePublish(self):
        self.force_publish_calls += 1


class FakeNumberEntity(FakeStateEntity):
    def __init__(self, value, min_value=15.0, max_value=30.0):
        super().__init__(value)
        self.min = min_value
        self.max = max_value


class ControllerScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_client_module = types.ModuleType("paho.mqtt.client")
        fake_client_module.Client = FakePahoClient
        fake_client_module.MQTTMessage = type("MQTTMessage", (), {})

        fake_mqtt_module = types.ModuleType("paho.mqtt")
        fake_mqtt_module.client = fake_client_module

        fake_paho_module = types.ModuleType("paho")
        fake_paho_module.mqtt = fake_mqtt_module

        cls._module_patches = {
            "paho": fake_paho_module,
            "paho.mqtt": fake_mqtt_module,
            "paho.mqtt.client": fake_client_module,
            "rgpio_sht4x": types.SimpleNamespace(SHT4x=FakeSHT4x),
            "simple_pid": types.SimpleNamespace(PID=FakePID),
            "dual_mc33926": types.SimpleNamespace(Motors=lambda **kwargs: None),
            "rgpio_ads1115": types.SimpleNamespace(ADS1115=lambda **kwargs: None),
            "rgpio": types.SimpleNamespace(error=RuntimeError),
        }
        cls._original_modules = {
            name: sys.modules.get(name) for name in cls._module_patches
        }
        sys.modules.update(cls._module_patches)
        cls.controller_module = importlib.import_module("internals.controller")
        cls.controller_module = importlib.reload(cls.controller_module)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("internals.controller", None)
        for name, original in cls._original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def make_controller_stub(self):
        controller = self.controller_module.Controller.__new__(self.controller_module.Controller)
        controller.schedule = []
        controller.schedule_slots = []
        controller.schedulesummary = FakeStateEntity("empty")
        controller.currentschedule = FakeStateEntity("none")
        controller.pid = FakePID(1.0, 1.0, 1.0, 0.0, (0, 1), True)
        controller.climate = FakeStateEntity(0.0)
        controller.desiredtemp = FakeStateEntity(0.0)
        controller.mode = "off"
        controller.currentsched = ""
        return controller

    def test_fetchsched_matches_exact_timestamp(self):
        controller = self.make_controller_stub()
        controller.schedule = [
            {"timestamp": "06:00", "temp": 21.0},
            {"timestamp": "22:30", "temp": 18.0},
        ]

        sched = controller.fetchsched("06:00")

        self.assertEqual(sched, {"timestamp": "06:00", "temp": 21.0})

    def test_rebuild_schedule_sorts_slots_and_applies_auto_mode(self):
        controller = self.make_controller_stub()
        controller.mode = "auto"
        controller.schedule_slots = [
            {"time": FakeStateEntity("22:30"), "temp": FakeNumberEntity(18.0)},
            {"time": FakeStateEntity("06:00"), "temp": FakeNumberEntity(21.0)},
            {"time": FakeStateEntity(""), "temp": FakeNumberEntity(19.0)},
        ]

        original_strftime = self.controller_module.time.strftime
        self.controller_module.time.strftime = lambda fmt: "06:00"
        try:
            controller._rebuild_schedule()
        finally:
            self.controller_module.time.strftime = original_strftime

        self.assertEqual(
            controller.schedule,
            [
                {"timestamp": "06:00", "temp": 21.0},
                {"timestamp": "22:30", "temp": 18.0},
            ],
        )
        self.assertEqual(controller.schedulesummary.value, "06:00 21.0, 22:30 18.0")
        self.assertEqual(controller.currentschedule.value, "06:00 21.0")
        self.assertEqual(controller.pid.setpoint, 21.0)
        self.assertEqual(controller.climate.value, 21.0)
        self.assertEqual(controller.desiredtemp.value, 21.0)
        self.assertEqual(controller.currentsched, "06:00")

    def test_invalid_schedule_time_is_rejected(self):
        controller = self.make_controller_stub()
        time_entity = FakeStateEntity("06:00")
        controller.schedule_slots = [
            {"time": time_entity, "temp": FakeNumberEntity(21.0)},
        ]

        controller.handle_set_schedule_time(0, "bad")

        self.assertEqual(time_entity.value, "06:00")
        self.assertEqual(time_entity.force_publish_calls, 1)


if __name__ == "__main__":
    unittest.main()
