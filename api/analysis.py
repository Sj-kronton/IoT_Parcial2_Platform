import json, os, re, time
from typing import Optional
from zoneinfo import ZoneInfo
import psycopg2, psycopg2.extras, requests
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

TOKEN = os.environ["PANEL_TOKEN"]
GKEY = os.getenv("GEMINI_API_KEY", "")
GMODEL = os.getenv("GEMINI_MODEL", "").replace("models/", "")
TZ = ZoneInfo("America/Bogota")
router = APIRouter(prefix="/api")


def auth(x_token: Optional[str] = Header(None)):
    if x_token != TOKEN:
        raise HTTPException(401, "token invalido")


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


def ensure_table():
    try:
        conn = db()
        with conn, conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS analysis_log(
                id serial PRIMARY KEY, time timestamptz DEFAULT now(), device_id text,
                hours int, model text, result text, stats jsonb)""")
        conn.close()
    except Exception as e:
        print("analysis_log:", e, flush=True)


ensure_table()


def rd(x, n=3):
    return None if x is None else round(float(x), n)


def fmt(t):
    return t.astimezone(TZ).strftime("%d/%m %H:%M")


def dev_stats(dev, hours, detail=True):
    secs = hours * 3600
    rows = query("""SELECT variable, max(unit) unit, count(*) n, avg(value) avg, min(value) min,
        max(value) max, stddev(value) std,
        (array_agg(value ORDER BY time ASC))[1] first, (array_agg(value ORDER BY time DESC))[1] last,
        (array_agg(time ORDER BY value ASC))[1] t_min, (array_agg(time ORDER BY value DESC))[1] t_max
        FROM measurements WHERE device_id=%s AND time > now() - make_interval(secs => %s)
        GROUP BY variable ORDER BY variable""", (dev, secs))
    out = {}
    for r in rows:
        v = {"unidad": r["unit"], "muestras": r["n"], "promedio": rd(r["avg"]), "minimo": rd(r["min"]),
             "hora_minimo": fmt(r["t_min"]), "maximo": rd(r["max"]), "hora_maximo": fmt(r["t_max"]),
             "desv_estandar": rd(r["std"]), "primer_valor": rd(r["first"]), "ultimo_valor": rd(r["last"])}
        out[r["variable"]] = v
    if detail and out:
        step = max(60, secs / 36)
        for r in query("""SELECT variable, time_bucket(make_interval(secs => %s), time) b, avg(value) v
                FROM measurements WHERE device_id=%s AND time > now() - make_interval(secs => %s)
                GROUP BY 1,2 ORDER BY 1,2""", (step, dev, secs)):
            out[r["variable"]].setdefault("serie", []).append([fmt(r["b"]), rd(r["v"], 2)])
        if hours >= 24:
            for r in query("""SELECT variable, extract(hour FROM time AT TIME ZONE 'America/Bogota')::int h, avg(value) v
                    FROM measurements WHERE device_id=%s AND time > now() - make_interval(secs => %s)
                    GROUP BY 1,2 ORDER BY 1,2""", (dev, secs)):
                out[r["variable"]].setdefault("promedio_por_hora_del_dia", {})[r["h"]] = rd(r["v"], 2)
    return out


def events(dev, hours):
    rows = query("""SELECT time, action, value, who FROM command_log
        WHERE device_id=%s AND who='panel' AND time > now() - make_interval(secs => %s)
        ORDER BY time LIMIT 30""", (dev, hours * 3600))
    return [f"{fmt(r['time'])} {r['action']} {r['value']}" for r in rows]


def gemini(prompt):
    if not GKEY or not GMODEL:
        raise HTTPException(500, "Falta GEMINI_API_KEY o GEMINI_MODEL en .env")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GMODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3}}
    r = None
    for i in range(3):
        r = requests.post(url, headers={"x-goog-api-key": GKEY}, json=body, timeout=90)
        if r.status_code in (429, 503):
            time.sleep(15 * (i + 1))
            continue
        break
    if r.status_code != 200:
        raise HTTPException(502, f"Gemini {r.status_code}: {r.text[:300]}")
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


INSTR = """Eres analista de datos IoT. Escribe en espanol, tono tecnico y claro, para un informe universitario.
Usa SOLO los datos suministrados; no inventes valores ni causas que los datos no respalden, y si algo es
incierto dilo. Indica siempre horas (zona America/Bogota) y unidades. Estructura la respuesta asi:
1. Resumen (2-3 frases). 2. Comportamiento por variable: tendencia, ciclo dia/noche si lo hay, picos y valles
con su hora, variabilidad. 3. Anomalias y relacion con los comandos enviados (calibraciones, apagados,
cambios de intervalo): un escalon o hueco puede deberse a ellos. 4. Reglas/alertas sugeridas con umbrales
razonables. 5. Conclusion. Ten en cuenta que los dispositivos 'twin' son simulaciones, 'dataset' son
repeticiones de datos historicos, 'api' vienen de servicios externos y 'real' miden la VM de Azure."""


class Req(BaseModel):
    device_id: str = "ALL"
    hours: int = 24


@router.post("/analysis", dependencies=[Depends(auth)])
def analyze(req: Req):
    hours = max(1, min(req.hours, 24 * 14))
    dev = req.device_id
    if dev != "ALL" and not re.fullmatch(r"[TRAD]\d+", dev):
        raise HTTPException(400, "dispositivo invalido")
    if dev == "ALL":
        ids = [r["device_id"] for r in query("SELECT DISTINCT device_id FROM measurements ORDER BY 1")]
        stats = {d: dev_stats(d, hours, detail=False) for d in ids}
        ctx = "Resumen general de todos los dispositivos en las ultimas %d horas. Compara dispositivos y busca relaciones."
        data = {"periodo_horas": hours, "dispositivos": stats}
    else:
        meta = query("SELECT name, kind, protocol FROM devices WHERE device_id=%s", (dev,))
        stats = dev_stats(dev, hours)
        if not stats:
            raise HTTPException(404, "sin datos en ese periodo")
        ctx = "Analisis del dispositivo %s en las ultimas %%d horas." % dev
        data = {"dispositivo": dev, "info": meta[0] if meta else {}, "periodo_horas": hours,
                "variables": stats, "comandos_en_el_periodo": events(dev, hours)}
    prompt = f"{INSTR}\n\n{ctx % hours}\n\nDATOS (JSON):\n{json.dumps(data, ensure_ascii=False)}"
    text = gemini(prompt)
    conn = db()
    with conn, conn.cursor() as cur:
        cur.execute("INSERT INTO analysis_log(device_id,hours,model,result,stats) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (dev, hours, GMODEL, text, json.dumps(data)))
        new_id = cur.fetchone()[0]
    conn.close()
    return {"id": new_id, "device_id": dev, "hours": hours, "model": GMODEL, "text": text}


@router.get("/analysis/history", dependencies=[Depends(auth)])
def history(device_id: Optional[str] = None, limit: int = 15):
    if device_id:
        rows = query("SELECT id,time,device_id,hours,model,result FROM analysis_log WHERE device_id=%s ORDER BY time DESC LIMIT %s",
                     (device_id, min(limit, 100)))
    else:
        rows = query("SELECT id,time,device_id,hours,model,result FROM analysis_log ORDER BY time DESC LIMIT %s",
                     (min(limit, 100),))
    for r in rows:
        r["time"] = r["time"].isoformat()
    return rows
