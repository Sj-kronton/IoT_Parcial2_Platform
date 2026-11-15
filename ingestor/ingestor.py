import json, os, time
import paho.mqtt.client as mqtt
import psycopg2


def connect_db():
    while True:
        try:
            c = psycopg2.connect(host=os.getenv("PG_HOST", "timescaledb"), dbname="iot",
                                 user="postgres", password=os.environ["PG_PASSWORD"])
            c.autocommit = True
            print("DB conectada", flush=True)
            return c
        except Exception as e:
            print("esperando DB:", e, flush=True)
            time.sleep(3)


conn = connect_db()


def run(sql, rows):
    global conn
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
    except Exception as e:
        print("error DB:", e, flush=True)
        try:
            conn.close()
        except Exception:
            pass
        conn = connect_db()


def on_connect(c, u, f, rc, p):
    print("MQTT conectado:", rc, flush=True)
    for t in ("campus/+/+/telemetry", "campus/+/+/state", "campus/+/+/ack"):
        c.subscribe(t, qos=1)


def on_message(c, u, msg):
    try:
        _, kind, dev, channel = msg.topic.split("/")
        d = json.loads(msg.payload)
    except Exception:
        return
    if channel == "telemetry":
        units = d.get("units", {})
        rows = [(d.get("ts"), dev, k, float(v), units.get(k)) for k, v in d.get("vars", {}).items()]
        run("INSERT INTO devices(device_id, kind) VALUES (%s,%s) ON CONFLICT DO NOTHING", [(dev, kind)])
        run("INSERT INTO measurements(time, device_id, variable, value, unit) VALUES (%s,%s,%s,%s,%s)", rows)
    elif channel == "state" and "name" in d:
        run("""INSERT INTO devices(device_id, name, kind, protocol, enabled) VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (device_id) DO UPDATE SET name=EXCLUDED.name, kind=EXCLUDED.kind,
               protocol=EXCLUDED.protocol, enabled=EXCLUDED.enabled""",
            [(dev, d["name"], kind, d.get("protocol"), d.get("enabled", True))])
    elif channel == "ack":
        run("INSERT INTO command_log(device_id, action, value, who, ack) VALUES (%s,%s,%s,%s,%s)",
            [(dev, d.get("action"), str(d.get("value")), "device-ack", d.get("ok"))])


c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ingestor")
c.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASS"])
c.on_connect, c.on_message = on_connect, on_message
while True:
    try:
        c.connect(os.getenv("MQTT_HOST", "emqx"), 1883, 30)
        break
    except Exception as e:
        print("esperando broker:", e, flush=True)
        time.sleep(5)
c.loop_forever()
