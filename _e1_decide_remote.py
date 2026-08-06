"""Remote-side: decision dataset for stop-now vs let-finish.

Per lane: grade counts, timeout-INCONCLUSIVE ids/kernels, remaining
(never-run) probes per kernel, per-kernel observed timeout rate.
Also checks global + lane0/1 for any timed-out INCONCLUSIVE.
"""
import json
from collections import Counter
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")


def rows_of(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def is_requeueable(r):
    return (
        r.get("evidence_grade") == "INCONCLUSIVE"
        and (r.get("timed_out") is True
             or r.get("inconclusive_class") in ("timeout", "out_of_memory"))
    )


survivors_by_kernel = {}
for line in open(E1 / "baseline_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if row.get("status") == "survived":
        survivors_by_kernel.setdefault(row["kernel"], []).append(row["probe_id"])

all_done = set()
sources = {"global": E1 / "equiv_observations.jsonl"}
for lane in (0, 1, 2, 3):
    sources[f"lane{lane}"] = E1 / f"equiv_observations_lane{lane}.jsonl"

requeue_total = 0
for name, path in sources.items():
    rows = rows_of(path)
    grades = Counter(r["evidence_grade"] for r in rows)
    req = [r for r in rows if is_requeueable(r)]
    requeue_total += len(req)
    all_done |= {r["probe_id"] for r in rows}
    print(f"{name}: n={len(rows)} grades={dict(grades)} requeueable={len(req)}")
    if req:
        by_kernel = Counter(r["kernel"] for r in req)
        walls = sorted(r["wall_ms"] / 1000 for r in req)
        print(f"  requeue kernels: {dict(by_kernel)}")
        print(f"  wall median {walls[len(walls)//2]:.0f}s")
        vr = Counter((r.get("evidence") or {}).get("random_rounds_passed", "?")
                     for r in req)
        sr = Counter((r.get("evidence") or {}).get("stress_rounds_passed", "?")
                     for r in req)
        print(f"  random_passed dist: {dict(vr)}  stress_passed dist: {dict(sr)}")

never_run = {k: [p for p in pids if p not in all_done]
             for k, pids in survivors_by_kernel.items()}
never_run = {k: v for k, v in never_run.items() if v}
print("never_run per kernel:", {k: len(v) for k, v in sorted(never_run.items())})
print("never_run total:", sum(len(v) for v in never_run.values()))

# per-kernel timeout rate among lanes 2/3 observations (for option-B estimate)
rate = {}
for lane in (2, 3):
    for r in rows_of(E1 / f"equiv_observations_lane{lane}.jsonl"):
        k = r["kernel"]
        tot, to = rate.get(k, (0, 0))
        rate[k] = (tot + 1, to + (1 if is_requeueable(r) else 0))
print("kernel timeout rates (obs, timeouts):",
      {k: v for k, v in sorted(rate.items())})
print("account: done_union", len(all_done), "of 527; remaining",
      527 - len(all_done))
print("DECIDE_DONE")
