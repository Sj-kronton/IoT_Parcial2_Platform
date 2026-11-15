import csv, glob
from common import Device


def find(pattern):
    f = glob.glob(f"/app/data/**/{pattern}", recursive=True)
    if not f:
        raise FileNotFoundError(f"No encontre {pattern} en devices/data")
    return f[0]


def num(x, comma=False):
    try:
        v = float(str(x).replace(",", ".") if comma else x)
    except Exception:
        return None
    return None if v == -200 else v


class Replay(Device):
    kind = "dataset"
    protocol = "MQTT (replay de CSV)"
    default_interval = 15
    pattern, delim, comma, cols = "", ",", False, {}

    def __init__(self, device_id):
        super().__init__(device_id)
        self.i = 0
        with open(find(self.pattern), newline="", encoding="utf-8", errors="ignore") as f:
            self.rows = list(csv.DictReader(f, delimiter=self.delim))
        print(device_id, len(self.rows), "filas cargadas", flush=True)

    def read(self):
        r = self.rows[self.i % len(self.rows)]
        self.i += 1
        return {k: num(r.get(c), self.comma) for k, c in self.cols.items()}

    def extra_state(self):
        return {"row": self.i % len(self.rows), "total": len(self.rows)}

    def custom_cmd(self, a, v):
        if a == "restart":
            self.i = 0
            return True
        return False


class D1(Replay):
    title = "UCI Air Quality - dataset historico"
    pattern, delim, comma = "AirQualityUCI*.csv", ";", True
    cols = {"co": "CO(GT)", "benzene": "C6H6(GT)", "nox": "NOx(GT)", "no2": "NO2(GT)",
            "temp": "T", "hum": "RH"}
    units = {"co": "mg/m3", "benzene": "ug/m3", "nox": "ppb", "no2": "ug/m3", "temp": "C", "hum": "%"}


class D2(Replay):
    title = "UCI Appliances Energy - dataset historico"
    pattern = "energydata_complete*.csv"
    cols = {"appliances_wh": "Appliances", "lights_wh": "lights", "t_indoor": "T1",
            "rh_indoor": "RH_1", "t_out": "T_out"}
    units = {"appliances_wh": "Wh", "lights_wh": "Wh", "t_indoor": "C", "rh_indoor": "%", "t_out": "C"}
