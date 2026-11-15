import os, time
from twins import T1, T2, T3
from real import R1, R2, R3
from apis import A1, A2, A3
from datasets import D1, D2

REG = {"T1": T1, "T2": T2, "T3": T3, "R1": R1, "R2": R2, "R3": R3,
       "A1": A1, "A2": A2, "A3": A3, "D1": D1, "D2": D2}

for did in os.environ["DEVICES"].split(","):
    did = did.strip()
    REG[did](did).start()
    print("iniciado", did, flush=True)

while True:
    time.sleep(3600)
