import json, os, re
from typing import Optional, Union
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import psycopg2
import psycopg2.extras

TOKEN = os.environ["PANEL_TOKEN"]
KINDS = {"T": "twin", "R": "real", "A": "api", "D": "dataset"}
ACTIONS = {"set_interval", "power", "calibrate", "reset_calibration", "setpoint",
           "hvac", "pump", "auto", "restart"}
STATES = {}

# ---------- MQTT ----------
def on_connect(c, u, f, rc, p):
    print("API MQTT conectado:", rc, flush=True)
    c.subscribe("campus/+/+/state", qos=1)


def on_message(c, u, msg):
    try:
        dev = msg.topic.split("/")[2]
        STATES[dev] = json.loads(msg.payload)
    except Exception:
        pass


mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="api-control")
mq.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASS"])
mq.on_connect, mq.on_message = on_connect, on_message
mq.connect_async(os.getenv("MQTT_HOST", "emqx"), 1883, 30)
mq.loop_start()

# ---------- DB ----------
def db():
    return psycopg2.connect(host=os.getenv("PG_HOST", "timescaledb"), dbname="iot",
                            user="postgres", password=os.environ["PG_PASSWORD"])


def query(sql, args=None):
    conn = db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


# ---------- API ----------
def auth(x_token: Optional[str] = Header(None)):
    if x_token != TOKEN:
        raise HTTPException(401, "token invalido")


app = FastAPI(title="IoT Campus UNAB")
r = APIRouter(prefix="/api")


class Cmd(BaseModel):
    action: str
    value: Union[float, str, None] = None
    variable: Optional[str] = None


@r.get("/health")
def health():
    return {"ok": True, "mqtt": mq.is_connected(), "devices_con_estado": len(STATES)}


@r.get("/devices", dependencies=[Depends(auth)])
def devices():
    rows = query("""SELECT DISTINCT ON (device_id, variable) device_id, variable, value, unit, time
                    FROM measurements WHERE time > now() - interval '6 hours'
                    ORDER BY device_id, variable, time DESC""")
    out = {}
    for x in rows:
        d = out.setdefault(x["device_id"], {"id": x["device_id"], "values": {}, "last": None})
        d["values"][x["variable"]] = {"value": x["value"], "unit": x["unit"]}
        t = x["time"].isoformat()
        if d["last"] is None or t > d["last"]:
            d["last"] = t
    for dev, st in STATES.items():
        out.setdefault(dev, {"id": dev, "values": {}, "last": None})
    for dev, d in out.items():
        d["state"] = STATES.get(dev, {})
        d["kind"] = KINDS.get(dev[:1], "?")
    return sorted(out.values(), key=lambda d: d["id"])


@r.post("/devices/{dev}/cmd", dependencies=[Depends(auth)])
def send_cmd(dev: str, cmd: Cmd):
    if not re.fullmatch(r"[TRAD]\d+", dev):
        raise HTTPException(400, "dispositivo invalido")
    if cmd.action not in ACTIONS:
        raise HTTPException(400, "accion no permitida")
    payload = {"action": cmd.action, "value": cmd.value}
    if cmd.variable:
        payload["variable"] = cmd.variable
    info = mq.publish(f"campus/{KINDS[dev[0]]}/{dev}/cmd", json.dumps(payload), qos=1)
    ok = info.rc == 0
    try:
        conn = db()
        with conn, conn.cursor() as cur:
            cur.execute("INSERT INTO command_log(device_id, action, value, who, ack) VALUES (%s,%s,%s,%s,%s)",
                        (dev, cmd.action, str(cmd.value), "panel", None))
        conn.close()
    except Exception as e:
        print("log error:", e, flush=True)
    return {"ok": ok, "sent": payload}


@r.get("/log", dependencies=[Depends(auth)])
def log(limit: int = 30):
    rows = query("SELECT time, device_id, action, value, who, ack FROM command_log ORDER BY time DESC LIMIT %s",
                 (min(limit, 200),))
    for x in rows:
        x["time"] = x["time"].isoformat()
    return rows


app.include_router(r)

from analysis import router as analysis_router
app.include_router(analysis_router)
