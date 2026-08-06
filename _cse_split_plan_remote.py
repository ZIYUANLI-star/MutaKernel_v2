"""Remote-side: evidence-based split of CSE lane0 into serial + 2 parallel.

Classification (classify_vram_evidence, conservative):
  PROVEN_UNSAFE  resource/OOM history anywhere, or known-unsafe list
                 (L1_P39 measured 41.8GB; L1_P21 lane0-era incident)
  PROVEN_SAFE    completed probes under a 0.45-fraction equiv lane
                 (36.9GB cap) with zero resource events and zero 0.45-era
                 timeouts -> proven peak <= 36.9GB -> may run two-wide
  UNKNOWN        only high-fraction (0.9 requeue) or serial-era history
                 -> stays serial

Appends lanes[3] (serial 0.92) + lanes[4]/[5] (parallel 0.45 each,
0.45+0.45 <= 0.92 red line) to cse_lane_plan.json.  lanes[0..2] untouched.
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
from scripts.run_e1_cse_falsify import classify_vram_evidence  # noqa: E402
from scripts.run_e1_probe_study import plan_equiv_lanes  # noqa: E402

E1 = Path("/root/mk_v2_runs/e1")
RESOURCE_MARKER = "resource/infrastructure limit"
KNOWN_UNSAFE = ("L1_P39", "L1_P21")
CAPPED45_OBS = [E1 / f"equiv_observations_lane{n}.jsonl" for n in (0, 1, 2, 3)]
ALL_HISTORY = ([E1 / "equiv_observations.jsonl",
                E1 / "equiv_observations_lane4_requeue.jsonl",
                E1 / "equiv_observations_timeout_v1.jsonl",
                E1 / "equiv_observations_timeout_v2.jsonl"] + CAPPED45_OBS)


def rows_of(path):
    if not path.exists():
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        if line.strip():
            out.append((json.loads(line), line))
    return out


plan_path = E1 / "cse_lane_plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8"))
if len(plan["lanes"]) != 3:
    raise SystemExit(f"REFUSE: expected 3 CSE lanes, got {len(plan['lanes'])}")
lane0_kernels = list(plan["lanes"][0]["kernels"])

resource_kernels = set()
for path in ALL_HISTORY:
    for row, line in rows_of(path):
        if RESOURCE_MARKER in line or row.get("inconclusive_class") == "out_of_memory":
            resource_kernels.add(row["kernel"])

capped_complete, capped_timeout = set(), set()
for path in CAPPED45_OBS:
    for row, _ in rows_of(path):
        if row.get("timed_out"):
            capped_timeout.add(row["kernel"])
        else:
            capped_complete.add(row["kernel"])
# The v2 timeout archive holds 0.45-era whole-probe timeouts (lanes 0/2/3).
for row, _ in rows_of(E1 / "equiv_observations_timeout_v2.jsonl"):
    capped_timeout.add(row["kernel"])

history = {
    k: {
        "resource_events": k in resource_kernels,
        "capped45_complete": k in capped_complete,
        "capped45_timeout": k in capped_timeout,
    }
    for k in lane0_kernels
}
classes = classify_vram_evidence(history, known_unsafe=KNOWN_UNSAFE)

# --- remaining lane0 CSE targets ---
likely_by_kernel = {}
for row, _ in rows_of(E1 / "equiv_observations.jsonl"):
    if (row.get("evidence_grade") == "LIKELY_EQUIVALENT"
            and row["kernel"] in set(lane0_kernels)):
        likely_by_kernel.setdefault(row["kernel"], set()).add(row["probe_id"])

cse_done = set()
for f in sorted(E1.glob("cse_completed_lane*.json")):
    cse_done |= set(json.load(open(f)))
legacy = E1 / "cse_falsify_completed.json"
if legacy.exists():
    cse_done |= set(json.load(open(legacy)))

remaining = {k: sorted(p for p in pids if p not in cse_done)
             for k, pids in likely_by_kernel.items()}
remaining = {k: v for k, v in remaining.items() if v}
lane0_total = sum(len(p) for p in likely_by_kernel.values())
lane0_done = lane0_total - sum(len(v) for v in remaining.values())

# --- per-probe estimates from measured lane0 CSE walls ---
cse_walls = {}
for row, _ in rows_of(E1 / "cse_observations_lane0.jsonl"):
    cse_walls.setdefault(row["kernel"], []).append(row["wall_ms"] / 1000)
all_walls = [w for ws in cse_walls.values() for w in ws]
global_med = statistics.median(all_walls) if all_walls else 1200.0

loads = {}
for kernel, pids in remaining.items():
    est = statistics.median(cse_walls[kernel]) if kernel in cse_walls else global_med
    loads[kernel] = min(1800.0, est) * len(pids)

serial = sorted((k for k in remaining if classes[k] != "PROVEN_SAFE"),
                key=lambda k: (-loads[k], k))
safe_loads = {k: loads[k] for k in remaining if classes[k] == "PROVEN_SAFE"}
par_lanes, par_totals = plan_equiv_lanes(safe_loads, [], n_lanes=2)
lanes = [serial, par_lanes[0], par_lanes[1]]
totals = [sum(loads[k] for k in serial), par_totals[0], par_totals[1]]

flat = [k for lane in lanes for k in lane]
assert len(flat) == len(set(flat)), "split lanes overlap"
assert set(flat) == set(remaining), "split lanes != remaining lane0 kernels"
assert lane0_done + sum(len(remaining[k]) for k in flat) == lane0_total == 206, (
    f"account: done={lane0_done} remaining={sum(len(v) for v in remaining.values())}")

roles = ["heavy-serial-v2 (0.92)", "safe-parallel (0.45)", "safe-parallel (0.45)"]
for i in range(3):
    plan["lanes"].append({
        "lane": 3 + i,
        "role": roles[i],
        "kernels": lanes[i],
        "kernel_count": len(lanes[i]),
        "probe_count": sum(len(remaining[k]) for k in lanes[i]),
        "est_seconds": round(totals[i], 1),
        "est_hours": round(totals[i] / 3600, 2),
        "split_from": 0,
    })
plan["version"] = 2
plan["v2_created_at"] = datetime.now(timezone.utc).isoformat()
plan["vram_classification"] = {
    k: {"class": classes[k], **history[k],
        "known_unsafe": k in KNOWN_UNSAFE,
        "remaining_probes": len(remaining.get(k, []))}
    for k in sorted(lane0_kernels)
}
plan_path.write_text(json.dumps(plan, indent=1), encoding="utf-8")

print("== per-kernel classification (evidence basis) ==")
for k in sorted(lane0_kernels):
    h, c = history[k], classes[k]
    basis = []
    if k in KNOWN_UNSAFE:
        basis.append("known_unsafe")
    if h["resource_events"]:
        basis.append("resource_history")
    if h["capped45_complete"]:
        basis.append("0.45_complete")
    if h["capped45_timeout"]:
        basis.append("0.45_timeout")
    print(f"{k}: {c} [{','.join(basis) or 'no_0.45_evidence'}] "
          f"remaining={len(remaining.get(k, []))}")
print(f"\nlane0 CSE: total=206 done={lane0_done} remaining={206 - lane0_done}")
for i, entry in enumerate(plan["lanes"][3:]):
    print(f"lane {entry['lane']} ({entry['role']}): kernels={entry['kernel_count']} "
          f"probes={entry['probe_count']} est={entry['est_hours']}h")
serial_eta = sum(totals) / 3600
split_eta = max(totals[0] / 3600, totals[1] / 3600, totals[2] / 3600)
print(f"ETA comparison: stay-serial={serial_eta:.1f}h vs "
      f"split=max(serial {totals[0]/3600:.1f}h, par {totals[1]/3600:.1f}h/"
      f"{totals[2]/3600:.1f}h)={split_eta:.1f}h")
print("CSE_SPLIT_PLAN_OK")
