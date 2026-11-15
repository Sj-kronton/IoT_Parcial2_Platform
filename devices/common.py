import json, os, threading, time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Device:
    kind = "twin"
    title = ""
    protocol = "MQTT"
    units = {}
    default_interval = 10
    extra_subs = ()

    def __init__(self, device_id):
        self.id = device_id
        self.interval = float(os.getenv(f"INTERVAL_{device_id}", self.default_interval))
        self.enabled = True
        self.offset = {}
        self.base = f"campus/{self.kind}/{device_id}"
        self._wake = threading.Event()
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"dev-{device_id}")
        c.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASS"])
        c.will_set(f"{self.base}/state", json.dumps({"online": False}), qos=1, retain=True)
        c.on_connect = self._on_connect
        c.on_message = self._on_message
        self.c = c

    # ---- ganchos que sobreescriben las subclases ----
    def read(self):
        raise NotImplementedError

    def extra_state(self):
        return {}

    def custom_cmd(self, action, value):
        return False

    def on_other(self, topic, data):
        pass

    # ---- MQTT ----
    def start(self):
        host = os.getenv("MQTT_HOST", "emqx")
        port = int(os.getenv("MQTT_PORT", "1883"))
        while True:
            try:
                self.c.connect(host, port, 30)
                break
            except Exception as e:
                print(self.id, "esperando broker:", e, flush=True)
                time.sleep(5)
        self.c.loop_start()
        threading.Thread(target=self._run, daemon=True).start()

    def _on_connect(self, c, userdata, flags, rc, props):
        print(self.id, "conexion MQTT:", rc, flush=True)
        c.subscribe(f"{self.base}/cmd", qos=1)
        for t in self.extra_subs:
            c.subscribe(t)
        self.publish_state()

    def publish_state(self):
        st = {"online": True, "name": self.title or self.id, "protocol": self.protocol,
              "enabled": self.enabled, "interval_s": self.interval,
              "offset": self.offset, **self.extra_state()}
        self.c.publish(f"{self.base}/state", json.dumps(st), qos=1, retain=True)

    def ack(self, ok, action, value):
        self.c.publish(f"{self.base}/ack",
                       json.dumps({"ok": ok, "action": action, "value": value, "ts": now_iso()}), qos=1)

    def _on_message(self, c, u, msg):
        try:
            data = json.loads(msg.payload)
        except Exception:
            return
        if msg.topic.endswith("/cmd"):
            self.handle_cmd(data)
        else:
            try:
                self.on_other(msg.topic, data)
            except Exception as e:
                print(self.id, "on_other error:", e, flush=True)

    def handle_cmd(self, cmd):
        a, v, ok = cmd.get("action"), cmd.get("value"), True
        try:
            if a == "set_interval":
                self.interval = max(1.0, float(v))
                self._wake.set()
            elif a == "power":
                self.enabled = str(v).lower() in ("on", "1", "true")
                self._wake.set()
            elif a == "calibrate":
                self.offset[cmd["variable"]] = float(v)
            elif a == "reset_calibration":
                self.offset = {}
            else:
                ok = self.custom_cmd(a, v)
        except Exception as e:
            print(self.id, "error comando:", e, flush=True)
            ok = False
        print(self.id, "cmd", a, v, "->", ok, flush=True)
        self.publish_state()
        self.ack(ok, a, v)

    def _run(self):
        while True:
            if self.enabled:
                try:
                    vals = self.read()
                    out = {k: round(float(x) + self.offset.get(k, 0.0), 3)
                           for k, x in vals.items() if x is not None}
                    if out:
                        self.c.publish(f"{self.base}/telemetry",
                                       json.dumps({"ts": now_iso(), "vars": out, "units": self.units}), qos=1)
                except Exception as e:
                    print(self.id, "error leyendo:", e, flush=True)
            self._wake.wait(self.interval)
            self._wake.clear()
