"""Remote-side: dual-lane status report (records, rates, memory, anomalies)."""
import json
import statistics
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
RUNS = Path("/root/mk_v2_runs")

for lane in ("4_requeue",):
    obs = E1 / f"equiv_observations_lane{lane}.jsonl"
    rows = ([json.loads(l) for l in open(obs, encoding="utf-8") if l.strip()]
            if obs.exists() else [])
    print(f"--- lane {lane}: {len(rows)} records ---")
    for r in rows:
        print(json.dumps({
            "probe_id": r["probe_id"], "grade": r["evidence_grade"],
            "wall_s": round(r["wall_ms"] / 1000),
            "timed_out": r["timed_out"],
            "valid_rounds": r.get("valid_rounds"),
            "evidence": r.get("evidence"),
        }))

mem_log = RUNS / "e1_mem_samples.log"
if mem_log.exists():
    vals = [int(l.split()[0]) for l in open(mem_log) if l.strip()]
    if vals:
        print(f"--- memory samples n={len(vals)} (MiB): max={max(vals)} "
              f"p95={sorted(vals)[int(0.95 * (len(vals) - 1))]} "
              f"mean={round(statistics.mean(vals))} ---")

for lane in ("4_requeue",):
    log = RUNS / f"e1_equiv_lane{lane}.log"
    bad = [l.strip() for l in open(log, encoding="utf-8", errors="replace")
           if any(m in l.lower() for m in ("out of memory", "traceback", "cuda error", "autorestart"))]
    print(f"--- lane {lane} log anomalies: {len(bad)} ---")
    for l in bad[:5]:
        print(" ", l[:200])
