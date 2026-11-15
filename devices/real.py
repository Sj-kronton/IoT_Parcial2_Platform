import os, socket, time
import psutil
from common import Device


class R1(Device):
    kind = "real"
    title = "VM Azure - salud del host (real)"
    default_interval = 15
    units = {"cpu": "%", "load1": "", "mem": "%", "disk": "%"}

    def __init__(self, device_id):
        super().__init__(device_id)
        psutil.cpu_percent(None)

    def read(self):
        return {"cpu": psutil.cpu_percent(None), "load1": os.getloadavg()[0],
                "mem": psutil.virtual_memory().percent, "disk": psutil.disk_usage("/").percent}


def _io():
    rx = tx = 0
    for name, c in psutil.net_io_counters(pernic=True).items():
        if name == "lo" or name.startswith(("docker", "br-", "veth")):
            continue
        rx += c.bytes_recv
        tx += c.bytes_sent
    return rx, tx


class R2(Device):
    kind = "real"
    title = "VM Azure - red (real)"
    default_interval = 15
    units = {"rx_kbps": "kbps", "tx_kbps": "kbps", "tcp_conn": "conn"}

    def __init__(self, device_id):
        super().__init__(device_id)
        self.last, self.t = _io(), time.time()

    def read(self):
        now, t = _io(), time.time()
        dt = max(t - self.t, 0.001)
        rx = (now[0] - self.last[0]) * 8 / 1000 / dt
        tx = (now[1] - self.last[1]) * 8 / 1000 / dt
        self.last, self.t = now, t
        return {"rx_kbps": rx, "tx_kbps": tx, "tcp_conn": len(psutil.net_connections(kind="tcp"))}


TARGETS = {"azuremaps_ms": ("atlas.microsoft.com", 443),
           "dns_ms": ("8.8.8.8", 53),
           "gps_ms": ("gpsmobile.co", 4000)}


def tcp_ms(host, port):
    t = time.time()
    try:
        socket.create_connection((host, port), timeout=3).close()
    except Exception:
        return None
    return (time.time() - t) * 1000


class R3(Device):
    kind = "real"
    title = "Sonda de red - latencia a servicios (real)"
    default_interval = 20
    units = {"azuremaps_ms": "ms", "dns_ms": "ms", "gps_ms": "ms", "probes_ok": "of 3"}

    def read(self):
        out = {k: tcp_ms(*v) for k, v in TARGETS.items()}
        out["probes_ok"] = sum(x is not None for x in out.values())
        return out
