import logging
import queue
import time
from typing import Optional

from rgpio_sht4x import SHT4x
from simple_pid import PID

from mqtt import ClimateEntity, MQTTClient, MQTTEntity, NumberEntity, TextEntity
from .motor import MoveThread
from .schedule import (
    format_schedule_row,
    normalize_schedule_timestamp,
    summarize_schedule,
)
from .threadinghelpers import SHUTDOWN_EV

_LOGGER = logging.getLogger(__name__)


def adj_tunings(t, index, data):
    t = list(t)  # (Kp, Ki, Kd)
    t[index] = float(data)
    return t[0], t[1], t[2]


class Controller:
    def __init__(self, client: MQTTClient, options):
        self.client = client
        self.manualposition = client.register_entity(NumberEntity("manualposition", "Manual Position", min_value=0, max_value=30000,
                                                                on_command=self.handle_set_position, value=0, unit="mm"))
        self.targetposition = client.register_entity(MQTTEntity("sensor", "targetposition", "Target Position", value=0, unit="mm"))
        self.actualposition = client.register_entity(MQTTEntity("sensor", "actualposition", "Actual Position", unit="mm"))
        self.kp = client.register_entity(NumberEntity("kp", "Proportional", min_value=0, max_value=64000, on_command=self.handle_set_proportional, value=1.5, unit="mm"))
        self.ki = client.register_entity(NumberEntity("ki", "Integral", min_value=0, max_value=100, on_command=self.handle_set_integral, value=1.2, unit="mm"))
        self.kd = client.register_entity(NumberEntity("kd", "Derivative", min_value=0, max_value=64000, on_command=self.handle_set_derivative, value=1.1, unit="mm"))
        self.ap = client.register_entity(MQTTEntity("sensor", "ap", "Calc'd Prop.", unit="mm"))
        self.ai = client.register_entity(MQTTEntity("sensor", "ai", "Calc'd Int.", unit="mm"))
        self.ad = client.register_entity(MQTTEntity("sensor", "ad", "Calc'd Deriv.", unit="mm"))
        self.desiredtemp = client.register_entity(MQTTEntity("sensor", "desiredtemp", "Desired Temp.", unit="°C", device_class="temperature"))
        self.actualtemp = client.register_entity(MQTTEntity("sensor", "actualtemperature", "Actual Temperature", unit="°C", device_class="temperature"))
        self.actualhumid = client.register_entity(MQTTEntity("sensor", "actualhumidity", "Actual Humidity", unit="%", device_class="humidity"))
        self.climate = ClimateEntity("climate", "Climate", on_temp_command=self.handle_set_temp, on_mode_command=self.handle_set_mode,
                                     min_temp=options.get("min_temp", 15.0), max_temp=options.get("max_temp", 30.0))
        client.register_entity(self.climate)
        self.schedulesummary = client.register_entity(MQTTEntity("sensor", "schedulesummary", "Schedule Summary", value="empty"))
        self.currentschedule = client.register_entity(MQTTEntity("sensor", "currentschedule", "Current Schedule", value="none"))

        self.pid = PID(self.kp.getFloat(), self.ki.getFloat(), self.kd.getFloat(), setpoint=self.climate.getFloat(),
                output_limits=(options["posmin"], options["posmax"]),
                auto_mode=True if self.climate.mode == "auto" or self.climate.mode == "heat" else False)
        self.TEMP = SHT4x(
            bus=options["i2c_bus"],
            host=options["rgpio_addr"],
            port=options["rgpio_port"],
        )
        # PID extra options.
        self.pid.sample_time = options["updaterate"]  # set PID update rate UPDATE_RATE
        self.pid.proportional_on_measurement = False
        self.pid.differential_on_measurement = False
        self.motorq = queue.Queue()
        self.controllerq = queue.Queue()
        self.mover = MoveThread(self.motorq, self.controllerq, options)
        self.mover.start()
        self.schedule = []
        self.schedule_slots: list[dict[str, object]] = []
        self._build_schedule_slots(options)
        self.lograte = options["lograte"]
        self.currentsched = ""
        self.mode: str = "off"
        self._rebuild_schedule()

    def _build_schedule_slots(self, options) -> None:
        default_temp = float(options.get("min_temp", 15.0))
        for index in range(options.get("schedule_slots", 6)):
            slot_index = index + 1
            initial = options["schedule"][index] if index < len(options["schedule"]) else None
            time_value = initial["timestamp"] if initial else ""
            temp_value = initial["temp"] if initial else default_temp
            time_entity = self.client.register_entity(
                TextEntity(
                    f"schedule_slot_{slot_index}_time",
                    f"Schedule Slot {slot_index} Time",
                    value=time_value,
                    min_length=0,
                    max_length=5,
                    pattern=r"^$|^([01]\d|2[0-3]):[0-5]\d$",
                    entity_category="config",
                    on_command=lambda data, idx=index: self.handle_set_schedule_time(idx, data),
                )
            )
            temp_entity = self.client.register_entity(
                NumberEntity(
                    f"schedule_slot_{slot_index}_temp",
                    f"Schedule Slot {slot_index} Temp",
                    min_value=options.get("min_temp", 15.0),
                    max_value=options.get("max_temp", 30.0),
                    step=0.1,
                    value=temp_value,
                    unit="°C",
                    entity_category="config",
                    on_command=lambda data, idx=index: self.handle_set_schedule_temp(idx, data),
                )
            )
            self.schedule_slots.append({"time": time_entity, "temp": temp_entity})

    def handle_set_temp(self, data):
        #expect json parsed data
        self.pid.setpoint = data
        self.climate.value = data
        self.desiredtemp.value = data

    def handle_set_mode(self, data):
        #expect string, it should be one of "off", "heat", or "auto"
        self.mode = data
        if self.mode in ["heat", "auto"]:
            self.pid.auto_mode = True
        else:
            self.pid.auto_mode = False
        self.climate.mode = data
        if self.mode == "auto":
            self.checkSetSchedule(force=True)

    def handle_set_position(self, data):
        #expect json parsed data
        if data > 0:
            self.climate.mode = "off"
            self.mode = "off"
            self.targetposition.value = data
            self.motorq.put(["P", data])

    # (Kp, Ki, Kd) expect json parsed data
    def handle_set_proportional(self, data):
        self.pid.tunings = adj_tunings(self.pid.tunings, 0, data)
        self.kp.value = data

    def handle_set_integral(self, data):
        self.pid.tunings = adj_tunings(self.pid.tunings, 1, data)
        self.ki.value = data

    def handle_set_derivative(self, data):
        self.pid.tunings = adj_tunings(self.pid.tunings, 2, data)
        self.kd.value = data

    def handle_set_schedule_time(self, slot_index: int, data) -> None:
        slot = self.schedule_slots[slot_index]
        try:
            normalized = normalize_schedule_timestamp(data)
        except (TypeError, ValueError):
            _LOGGER.warning("Ignoring invalid schedule time for slot %s: %r", slot_index + 1, data)
            slot["time"].forcePublish()
            return
        slot["time"].value = normalized
        self._rebuild_schedule()

    def handle_set_schedule_temp(self, slot_index: int, data) -> None:
        slot = self.schedule_slots[slot_index]
        try:
            temp = float(data)
        except (TypeError, ValueError):
            _LOGGER.warning("Ignoring invalid schedule temperature for slot %s: %r", slot_index + 1, data)
            slot["temp"].forcePublish()
            return
        if temp < slot["temp"].min or temp > slot["temp"].max:
            _LOGGER.warning(
                "Ignoring out-of-range schedule temperature for slot %s: %s",
                slot_index + 1,
                temp,
            )
            slot["temp"].forcePublish()
            return
        slot["temp"].value = temp
        self._rebuild_schedule()

    def _rebuild_schedule(self) -> None:
        schedule: list[dict] = []
        for slot in self.schedule_slots:
            timestamp = normalize_schedule_timestamp(slot["time"].value)
            if not timestamp:
                continue
            schedule.append(
                {
                    "timestamp": timestamp,
                    "temp": float(slot["temp"].value),
                }
            )
        schedule.sort(key=lambda entry: entry["timestamp"])
        self.schedule = schedule
        self.schedulesummary.value = summarize_schedule(schedule)
        self._update_current_schedule_state()
        if self.mode == "auto":
            self.checkSetSchedule(force=True)

    def _update_current_schedule_state(self) -> None:
        sched = self.fetchsched(time.strftime("%H:%M"))
        self.currentschedule.value = format_schedule_row(sched) if sched else "none"
        if sched is None:
            self.currentsched = ""

    def fetchsched(self, currtimestamp: str) -> Optional[dict]:
        """
        Return the row whose 'timestamp' is the latest time <= currtimestamp.
        Assumes:
        - self.schedule is sorted ascending by row["timestamp"] as "HH:MM".
        """
        curr: Optional[dict] = None
        for row in self.schedule:
            if currtimestamp >= row["timestamp"]:
                curr = row
        if curr is None and self.schedule:
            # wrap to last entry of previous day if no pick.
            curr = self.schedule[-1]
        return curr

    def checkSetSchedule(self, force: bool = False):
        currstamp = time.strftime("%H:%M")
        sched = self.fetchsched(currstamp)
        self.currentschedule.value = format_schedule_row(sched) if sched else "none"
        if sched:
            if force or sched["timestamp"] != self.currentsched or self.pid.setpoint != sched["temp"]:
                self.pid.setpoint = sched["temp"]
                self.climate.value = sched["temp"]
                self.desiredtemp.value = sched["temp"]
                self.currentsched = sched["timestamp"]
        else:
            self.currentsched = ""

    def loop(self):
        apos: int | None = None
        try:
            self.client.connect(SHUTDOWN_EV)
            if SHUTDOWN_EV.is_set():
                return
            self._rebuild_schedule()

            lastupdate = time.monotonic()
            lastschedcheck = lastupdate
            while not SHUTDOWN_EV.is_set():
                # process queue
                if not self.controllerq.empty():
                    try:
                        ev = self.controllerq.get_nowait()
                        size = 1
                        while ev:
                            if ev[0] == "AP":
                                apos = ev[1]
                            size += 1
                            ev = self.controllerq.get_nowait()
                        print(f"q size: {size}")
                    except queue.Empty:
                        pass
                currentupdate = time.monotonic()
                currentschedcheck = time.monotonic()
                # measure
                temp, humidity = self.TEMP.measurements
                temp = round(temp, 2)
                humidity = round(humidity, 2)
                # Do things...
                newpos = self.pid(temp)
                if newpos is not None:
                    newpos = round(newpos)
                if self.mode != "off" and newpos is not None:
                    self.targetposition.value = newpos  # store new location
                    # move to new setpoint
                    self.motorq.put(["P", newpos])
                SHUTDOWN_EV.wait(max(0.5 - (currentupdate - lastupdate), 0))  # pause at most 0.5 secs; keeps PID timing drift bounded.
                lastupdate = currentupdate
                if currentschedcheck - lastschedcheck > self.lograte:
                    # Log stats...
                    self.climate.current_temperature = temp
                    self.climate.current_humidity = humidity
                    self.actualtemp.value = temp
                    self.actualhumid.value = humidity
                    if apos is not None:
                        self.actualposition.value = apos
                        apos = None
                    # log PID component values:
                    components = self.pid.components
                    self.ap.value = round(components[0], 2)
                    self.ai.value = round(components[1], 2)
                    self.ad.value = round(components[2], 2)
                    if self.mode == "auto":
                        self.checkSetSchedule()
                    lastschedcheck = currentschedcheck
        except KeyboardInterrupt:
            SHUTDOWN_EV.set()
            _LOGGER.info("Keyboard interrupt, exiting...")
        finally:
            _LOGGER.info("Main thread waiting for worker to finish...")
            self.mover.join(timeout=5)
            try:
                self.TEMP.close()
            except Exception:
                _LOGGER.exception("Failed to close SHT4x")
            self.client.disconnect()
