"""Remote-side: calibrate the lane plan with measured per-probe times -> ETA."""
import json
import statistics
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
plan = json.loads((E1 / "lane_plan.json").read_text())
per = plan["per_kernel"]

factors = []
lane_actual = {}
for lane_entry in plan["lanes"]:
    lane = lane_entry["lane"]
    obs = E1 / f"equiv_observations_lane{lane}.jsonl"
    rows = ([json.loads(l) for l in open(obs, encoding="utf-8") if l.strip()]
            if obs.exists() else [])
    done_by_kernel = {}
    walls_by_kernel = {}
    for r in rows:
        done_by_kernel[r["kernel"]] = done_by_kernel.get(r["kernel"], 0) + 1
        walls_by_kernel.setdefault(r["kernel"], []).append(r["wall_ms"] / 1000)
    lane_actual[lane] = (done_by_kernel, walls_by_kernel)
    for k, walls in walls_by_kernel.items():
        factors.append(statistics.median(walls) / max(1.0, per[k]["per_probe_s"]))

calib = statistics.median(factors) if factors else 1.0
print(f"calibration factor (measured/planned, {len(factors)} kernels): {calib:.2f}")

for lane_entry in plan["lanes"]:
    lane = lane_entry["lane"]
    done_by_kernel, walls_by_kernel = lane_actual[lane]
    remaining_s = 0.0
    remaining_probes = 0
    for k in lane_entry["kernels"]:
        left = per[k]["remaining_probes"] - done_by_kernel.get(k, 0)
        if left <= 0:
            continue
        if k in walls_by_kernel:
            est = statistics.median(walls_by_kernel[k])
        else:
            est = min(900.0, per[k]["per_probe_s"] * calib)
        remaining_s += left * est
        remaining_probes += left
    print(f"lane {lane}: remaining_probes={remaining_probes} "
          f"calibrated_eta_h={remaining_s / 3600:.1f}")
