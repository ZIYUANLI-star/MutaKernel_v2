"""Idempotency test (foreground second instance must refuse) + heavy-tail evidence."""
import io

import _remote

HT = r'''
import json, collections, math
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
rows = {}
for p in sorted(OUT.glob("calibration_*lane*.jsonl")):
    for line in p.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["unit"]] = r

def percentile_upstream(errors, q=0.95):
    """calibrate_tolerance's quantile, recomputed for the record."""
    import torch
    t = torch.tensor(sorted(errors), dtype=torch.float64)
    return float(torch.quantile(t, q))

print("== per-unit control error distribution (the 18 kept units)")
hdr = "%-24s %-22s %10s %10s %10s %8s %6s"
print(hdr % ("unit", "status", "p95", "tol=p95x1.5", "max_abs", "distinct", "fail"))
detail = {}
for unit, r in sorted(rows.items()):
    if r["control_status"] not in ("calibrated_ok", "calibrated_heavy_tail",
                                   "controls_incomplete"):
        continue
    tk = r["task_key"]
    obs_path = OUT / "units" / unit / ("b9_%s_observations.jsonl" % tk)
    if not obs_path.is_file():
        print("%-24s %-22s  (no observations file)" % (unit, r["control_status"]))
        continue
    errs = []
    for line in obs_path.read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        b9 = o.get("b9")
        if b9 is not None and b9.get("failure_kind") in (None, "tolerance"):
            errs.append(float(b9["max_abs_err"]))
    if not errs:
        print("%-24s %-22s  (no comparable errors; kinds recorded as %s)"
              % (unit, r["control_status"], r.get("outcome_kinds")))
        continue
    p95 = percentile_upstream(errs)
    tol = r.get("calibrated_tol")
    mx = max(errs)
    distinct = sorted(set(errs))
    nfail = sum(1 for e in errs if tol is not None and e > tol)
    print(hdr % (unit, r["control_status"], "%.6g" % p95,
                 "%.6g" % (p95 * 1.5), "%.6g" % mx, len(distinct), nfail))
    detail[unit] = {"errors": errs, "distinct": distinct, "p95": p95,
                    "tol": tol, "max": mx, "nfail": nfail,
                    "status": r["control_status"], "dtype": r["dtype"]}

print("\n== heavy-tail units in full (discreteness evidence)")
for unit, d in sorted(detail.items()):
    if d["status"] != "calibrated_heavy_tail":
        continue
    hist = collections.Counter(d["errors"])
    print("  %s (%s)" % (unit, d["dtype"]))
    print("    32 control max-abs errors, value:count = %s"
          % sorted(hist.items()))
    print("    distinct values: %s" % d["distinct"])
    print("    p95=%.6g  tol=p95x1.5=%.6g  max=%.6g  -> %d/32 controls exceed tol"
          % (d["p95"], d["tol"], d["max"], d["nfail"]))
    ratio = d["max"] / d["tol"] if d["tol"] else float("nan")
    print("    max/tol = %.4f ; consecutive distinct values differ by a factor of %s"
          % (ratio, [round(b / a, 4) for a, b in zip(d["distinct"], d["distinct"][1:])]))

print("\n== fp16 discreteness check: are the error values fp16-representable grid points?")
for unit, d in sorted(detail.items()):
    if d["dtype"] != "float16":
        continue
    vals = d["distinct"]
    exps = [math.log2(v) if v > 0 else None for v in vals]
    print("  %-24s %-22s distinct=%s log2=%s"
          % (unit, d["status"], vals, [None if e is None else round(e, 4) for e in exps]))

print("\n== census for the report")
st = collections.Counter(r["control_status"] for r in rows.values())
print("  all statuses:", dict(st))
kept = [u for u, r in rows.items() if r["control_status"] in
        ("calibrated_ok", "calibrated_heavy_tail", "controls_incomplete")]
ht = [u for u, r in rows.items() if r["control_status"] == "calibrated_heavy_tail"]
inc = [u for u, r in rows.items() if r["control_status"] == "controls_incomplete"]
print("  kept units: %d ; heavy_tail: %d (%s) ; controls_incomplete: %d (%s)"
      % (len(kept), len(ht), ht, len(inc), inc))
by_dtype = collections.Counter(rows[u]["dtype"] for u in kept)
ht_dtype = collections.Counter(rows[u]["dtype"] for u in ht)
print("  kept by dtype:", dict(by_dtype), " heavy_tail by dtype:", dict(ht_dtype))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(HT.encode()), "/root/_h11_ht.py")
sftp.close()

print("#### idempotency: run a second instance in the FOREGROUND (must refuse and exit)")
_remote.run(c, "cd /root/mk_v2 && timeout 60 /root/miniconda3/bin/python -u "
               "_b9_chain_trigger.py; echo EXIT_CODE=$?", timeout=180)
print("\n#### trigger processes after the idempotency test (expect the original only)")
_remote.run(c, "/root/miniconda3/bin/python -c \"import sys; sys.path.insert(0,'/root/mk_v2');"
               "import _b9_chain_trigger as t;"
               "print(t.find_processes('_b9_chain_trigger.py'))\"", timeout=120)
print("\n#### heavy-tail evidence")
_remote.run(c, "/root/miniconda3/bin/python /root/_h11_ht.py", timeout=600)
c.close()
print("\nH11_DONE")
