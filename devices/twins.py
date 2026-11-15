import math, random
from datetime import datetime
from zoneinfo import ZoneInfo
from common import Device

TZ = ZoneInfo("America/Bogota")


def hour_now():
    n = datetime.now(TZ)
    return n.hour + n.minute / 60, n.weekday()


def occupancy_factor():
    h, wd = hour_now()
    if wd >= 5:
        return 0.15 if 9 <= h < 14 else 0.0
    if 7 <= h < 12 or 14 <= h < 20:
        return random.uniform(0.6, 1.0)
    if 12 <= h < 14:
        return 0.35
    return 0.0


def outside_temp():
    h, _ = hour_now()
    return 25 + 4 * math.sin((h - 9) / 24 * 2 * math.pi)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def is_on(v):
    return str(v).lower() in ("on", "1", "true")


class T1(Device):
    title = "Aula inteligente (digital twin)"
    units = {"temp": "C", "hum": "%", "co2": "ppm", "occupancy": "people"}

    def __init__(self, device_id):
        super().__init__(device_id)
        self.temp, self.hum, self.co2 = 25.0, 60.0, 450.0
        self.setpoint, self.hvac = 22.0, True

    def read(self):
        occ = round(35 * occupancy_factor())
        k = lambda tau: min(1.0, self.interval / tau)
        self.co2 = clamp(self.co2 + (420 + occ * 22 - self.co2) * k(600) + random.gauss(0, 4), 400, 2000)
        target = (self.setpoint + 0.05 * occ) if self.hvac else (outside_temp() + 0.06 * occ)
        self.temp += (target - self.temp) * k(900) + random.gauss(0, 0.05)
        self.hum = clamp(75 - (self.temp - 20) * 2 + random.gauss(0, 0.8), 30, 90)
        return {"temp": self.temp, "hum": self.hum, "co2": self.co2, "occupancy": occ}

    def custom_cmd(self, a, v):
        if a == "setpoint":
            self.setpoint = clamp(float(v), 16, 30)
            return True
        if a == "hvac":
            self.hvac = is_on(v)
            return True
        return False

    def extra_state(self):
        return {"setpoint": self.setpoint, "hvac": self.hvac}


class T2(Device):
    title = "Invernadero (digital twin)"
    units = {"soil": "%", "temp": "C", "pump": "bool"}
    extra_subs = ("campus/api/A1/telemetry",)

    def __init__(self, device_id):
        super().__init__(device_id)
        self.soil, self.pump, self.auto, self.rain = 55.0, False, True, 0.0

    def on_other(self, topic, data):
        self.rain = float(data.get("vars", {}).get("rain_mm", 0) or 0)

    def read(self):
        dt = self.interval
        temp = outside_temp() + 2 + random.gauss(0, 0.2)
        self.soil -= 0.00004 * max(temp - 10, 0) * dt
        self.soil += 0.0005 * self.rain * dt
        if self.auto:
            if self.soil < 30 and self.rain < 0.5:
                self.pump = True
            elif self.soil > 60 or self.rain >= 2:
                self.pump = False
        if self.pump:
            self.soil += 0.05 * dt
        self.soil = clamp(self.soil, 10, 90)
        return {"soil": self.soil, "temp": temp, "pump": 1 if self.pump else 0}

    def custom_cmd(self, a, v):
        if a == "pump":
            self.pump, self.auto = is_on(v), False
            return True
        if a == "auto":
            self.auto = is_on(v)
            return True
        return False

    def extra_state(self):
        return {"pump": self.pump, "auto": self.auto}


class T3(Device):
    title = "Medidor de energia del edificio (digital twin)"
    units = {"voltage": "V", "current": "A", "power": "kW", "energy": "kWh"}

    def __init__(self, device_id):
        super().__init__(device_id)
        self.kwh = 0.0

    def read(self):
        p = clamp(0.8 + 5.5 * occupancy_factor() + random.gauss(0, 0.08), 0.3, 7)
        v = 120 + random.gauss(0, 0.8)
        self.kwh += p * self.interval / 3600
        return {"voltage": v, "current": p * 1000 / v, "power": p, "energy": self.kwh}
