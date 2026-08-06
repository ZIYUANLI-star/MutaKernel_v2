"""Refit the B9 ETA from measured first-wave wall times.

Replaces the two prior rate anchors (which came from the pre-fix 16:38 run and
from a single extrapolated matmul unit) with rates implied by the wave-2 rows,
then re-simulates stage 1 and stage 2 under the deployed admission model.
Anything still driven by an un-measured size regime is labelled extrapolated.
"""
import io

import _remote

SCRIPT = r'''
import json, sys
from pathlib import Path
sys.path.insert(0, "/root/mk_v2")
import _b9_resume_prep as prep

OUT = Path("/root/mk_v2_runs/e3_b9_calib")

rows = []
for p in sorted(OUT.glob("calibration_v2_lane*.jsonl")):
    for line in p.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))

kept, requeued, fresh, queue = prep.build("table")
by_unit = {u["unit"]: u for u in (kept + requeued + fresh)}

print("=== measured first-wave units ===")
hdr = "%-22s %11s %11s %8s %9s %9s %7s %12s"
print(hdr % ("unit", "in_numel", "out_numel", "wall_s", "est_fast", "est_slow",
             "ratio", "rate elem/s"))
measured = []
for r in sorted(rows, key=lambda x: x["unit"]):
    u = by_unit.get(r["unit"], {})
    inn, out = u.get("in_numel", 0), u.get("out_numel", 0)
    wall = r.get("wall_s") or 0
    good = ("calibrated_ok", "calibrated_heavy_tail", "controls_incomplete")
    if not wall or r.get("control_status") not in good:
        continue
    rate = 32.0 * (inn + out) / wall
    measured.append({"unit": r["unit"], "in": inn, "out": out, "wall": wall,
                     "rate": rate, "fast": u.get("est_wall_s_fast"),
                     "slow": u.get("est_wall_s_slow"),
                     "reduction_heavy": u.get("reduction_heavy")})
    print(hdr % (r["unit"], "%.4g" % inn, "%.4g" % out, "%.1f" % wall,
                 str(u.get("est_wall_s_fast")), str(u.get("est_wall_s_slow")),
                 "%.2f" % (wall / max(1.0, u.get("est_wall_s_fast") or 1)),
                 "%.3g" % rate))

if not measured:
    print("(no completed units yet)")
    raise SystemExit(0)

rates = sorted(m["rate"] for m in measured)
print("\nimplied throughput: min=%.3g median=%.3g max=%.3g elem/s (n=%d)"
      % (rates[0], rates[len(rates) // 2], rates[-1], len(rates)))
print("prior anchors: fast %.3g (elementwise)  slow %.3g (fp64 matmul, "
      "extrapolated)" % (prep.ELEMENTWISE_RATE, prep.MATMUL_RATE))

big = [m for m in measured if m["out"] >= 5e8]
print("\nunits above 5e8 output elements measured so far: %d %s"
      % (len(big), [m["unit"] for m in big]))

stage1 = [u for u in queue if u["reserve_gb"] < 60.0]
stage2 = [u for u in queue if u["reserve_gb"] >= 60.0]
print("\nremaining queue: stage1=%d stage2=%d" % (len(stage1), len(stage2)))

def resim(subset, rate, label):
    for u in subset:
        elements = u["in_numel"] + u["out_numel"]
        u["_refit"] = max(prep.FLOOR_WALL_S, 32 * elements / rate)
    total = prep.simulate(subset, 2, 100.0, "_refit")
    print("   %-34s 2 lanes: %7.1f h" % (label, total / 3600))
    return total

print("\n=== re-simulation with measured rates (2 lanes, 100 GiB) ===")
for label, rate in (("slowest measured rate", rates[0]),
                    ("median measured rate", rates[len(rates) // 2]),
                    ("fastest measured rate", rates[-1]),
                    ("prior slow anchor (extrapolated)", prep.MATMUL_RATE)):
    print("  rate %.3g elem/s -- %s" % (rate, label))
    resim(stage1, rate, "stage 1 (%d units)" % len(stage1))
    resim(stage2, rate, "stage 2 (%d units)" % len(stage2))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_eta_refit.py")
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python /root/_eta_refit.py",
            timeout=600)
c.close()
