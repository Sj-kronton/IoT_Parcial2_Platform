import json, os
import requests
from common import Device

# A1 y A2 usan Open-Meteo (sin clave). Antes usaban Azure Maps, cuya cuenta fue bloqueada.
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


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
    title = "Open-Meteo - condiciones actuales (API)"
    default_interval = 300
    units = {"temp": "C", "hum": "%", "wind_kmh": "km/h", "uv": "", "pressure_mb": "mb",
             "cloud": "%", "rain_mm": "mm"}
    first = True

    def read(self):
        lat, lon = os.getenv("A1_QUERY", "7.1182633,-73.1113583").split(",")
        r = requests.get(WEATHER_URL, timeout=15, params={
            "latitude": lat.strip(), "longitude": lon.strip(),
            "current": "temperature_2m,relative_humidity_2m,surface_pressure,"
                       "wind_speed_10m,precipitation,cloud_cover,uv_index"})
        r.raise_for_status()
        res = r.json()["current"]
        if self.first:
            print(self.id, "ejemplo respuesta:", json.dumps(res)[:700], flush=True)
            self.first = False
        return {"temp": res.get("temperature_2m"), "hum": res.get("relative_humidity_2m"),
                "wind_kmh": res.get("wind_speed_10m"), "uv": res.get("uv_index"),
                "pressure_mb": res.get("surface_pressure"), "cloud": res.get("cloud_cover"),
                "rain_mm": res.get("precipitation") or 0.0}


class A2(Device):
    kind = "api"
    protocol = "REST -> MQTT"
    title = "Open-Meteo - calidad del aire (API)"
    default_interval = 600
    units = {"aqi": "", "pm25": "ug/m3", "pm10": "ug/m3", "o3": "ug/m3",
             "no2": "ug/m3", "co": "ug/m3", "so2": "ug/m3"}
    first = True

    def read(self):
        lat, lon = os.getenv("A2_QUERY", "7.117030478043361,-73.10533865426798").split(",")
        r = requests.get(AIR_URL, timeout=15, params={
            "latitude": lat.strip(), "longitude": lon.strip(),
            "current": "us_aqi,pm2_5,pm10,ozone,nitrogen_dioxide,carbon_monoxide,sulphur_dioxide"})
        r.raise_for_status()
        res = r.json()["current"]
        if self.first:
            print(self.id, "ejemplo respuesta:", json.dumps(res)[:700], flush=True)
            self.first = False
        return {"aqi": res.get("us_aqi"), "pm25": res.get("pm2_5"), "pm10": res.get("pm10"),
                "o3": res.get("ozone"), "no2": res.get("nitrogen_dioxide"),
                "co": res.get("carbon_monoxide"), "so2": res.get("sulphur_dioxide")}


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
