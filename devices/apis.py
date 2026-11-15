import json, os
import requests
from common import Device

KEY = os.getenv("AZMAPS_KEY", "")
BASE = "https://atlas.microsoft.com/weather"


def g(d, *path):
    for p in path:
        try:
            d = d[p]
        except Exception:
            return None
    return d


class A1(Device):
    kind = "api"
    protocol = "REST -> MQTT"
    title = "Azure Maps - condiciones actuales (API)"
    default_interval = 300
    units = {"temp": "C", "hum": "%", "wind_kmh": "km/h", "uv": "", "pressure_mb": "mb",
             "cloud": "%", "rain_mm": "mm"}
    first = True

    def read(self):
        r = requests.get(f"{BASE}/currentConditions/json", timeout=15, params={
            "api-version": "1.0", "query": os.getenv("A1_QUERY", "7.1182633,-73.1113583"),
            "subscription-key": KEY, "language": "es-MX"})
        r.raise_for_status()
        res = r.json()["results"][0]
        if self.first:
            print(self.id, "ejemplo respuesta:", json.dumps(res)[:700], flush=True)
            self.first = False
        return {"temp": g(res, "temperature", "value"), "hum": g(res, "relativeHumidity"),
                "wind_kmh": g(res, "wind", "speed", "value"), "uv": g(res, "uvIndex"),
                "pressure_mb": g(res, "pressure", "value"), "cloud": g(res, "cloudCover"),
                "rain_mm": g(res, "precipitationSummary", "pastHour", "value") or 0.0}


class A2(Device):
    kind = "api"
    protocol = "REST -> MQTT"
    title = "Azure Maps - calidad del aire (API)"
    default_interval = 600
    units = {"aqi": "", "pm25": "ug/m3", "pm10": "ug/m3", "o3": "ug/m3",
             "no2": "ug/m3", "co": "ug/m3", "so2": "ug/m3"}
    first = True

    def read(self):
        r = requests.get(f"{BASE}/airQuality/current/json", timeout=15, params={
            "api-version": "1.1", "query": os.getenv("A2_QUERY", "7.117030478043361,-73.10533865426798"),
            "subscription-key": KEY, "language": "es-MX", "pollutants": "true"})
        r.raise_for_status()
        res = r.json()["results"][0]
        if self.first:
            print(self.id, "ejemplo respuesta:", json.dumps(res)[:700], flush=True)
            self.first = False
        pol = {p.get("type"): g(p, "concentration", "value") for p in res.get("pollutants", [])}
        return {"aqi": res.get("index"), "pm25": pol.get("PM2.5"), "pm10": pol.get("PM10"),
                "o3": pol.get("O3"), "no2": pol.get("NO2"), "co": pol.get("CO"), "so2": pol.get("SO2")}


def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flatten(v, f"{prefix}{k}_"))
    elif isinstance(d, list):
        for i, v in enumerate(d[:3]):
            out.update(flatten(v, f"{prefix}{i}_"))
    elif isinstance(d, (int, float)) and not isinstance(d, bool):
        out[prefix.rstrip("_").lower()] = d
    return out


class A3(Device):
    kind = "api"
    protocol = "REST -> MQTT"
    title = "GPS Ruta UNAB (API)"
    default_interval = 15
    first = True

    def read(self):
        r = requests.get(os.getenv("GPS_URL", "http://gpsmobile.co:4000/api/DetalleVehiculo/97141/96365"),
                         auth=(os.getenv("GPS_USER", ""), os.getenv("GPS_PASS", "")), timeout=15)
        r.raise_for_status()
        data = r.json()
        if self.first:
            print(self.id, "ejemplo respuesta:", json.dumps(data)[:900], flush=True)
            self.first = False
        return dict(list(flatten(data).items())[:20])
