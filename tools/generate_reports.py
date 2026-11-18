import datetime, json, subprocess, sys, time

HOURS = int(sys.argv[1]) if len(sys.argv) > 1 else 144
env = dict(l.strip().split("=", 1) for l in open("/srv/iot/.env") if "=" in l and not l.startswith("#"))
D, T = env["DOMAIN"], env["PANEL_TOKEN"]


def call(path, body=None):
    cmd = ["curl", "-s", "--max-time", "150", "--resolve", f"{D}:443:127.0.0.1",
           "-H", f"X-Token: {T}", "-H", "Content-Type: application/json"]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    cmd.append(f"https://{D}{path}")
    return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)


ids = ["ALL"] + [d["id"] for d in call("/api/devices")]
name = f"/srv/iot/reports/analisis_{datetime.date.today()}_{HOURS}h.md"
with open(name, "w", encoding="utf-8") as f:
    f.write(f"# Analisis con IA - ultimas {HOURS} horas\n\n")
    for i in ids:
        print("analizando", i, flush=True)
        try:
            r = call("/api/analysis", {"device_id": i, "hours": HOURS})
            body = r.get("text") or f"ERROR: {r}"
            f.write(f"## {i}  (modelo {r.get('model', '?')})\n\n{body}\n\n---\n\n")
        except Exception as e:
            f.write(f"## {i}\n\nERROR: {e}\n\n---\n\n")
        time.sleep(10)
print("listo ->", name)
