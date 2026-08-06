"""Snapshot: lane0/lane1 progress, processes, per-kernel lane0 medians."""
import _remote

REMOTE_SNAP = r'''
import json, statistics
from pathlib import Path
E1 = Path("/root/mk_v2_runs/e1")

def rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if p.exists() else []

def done(p):
    return json.load(open(p)) if p.exists() else []

g = done(E1/"equiv_completed.json")
l0 = done(E1/"equiv_completed_lane0.json")
l1 = done(E1/"equiv_completed_lane1.json")
print("completed: global", len(g), "lane0", len(l0), "lane1", len(l1),
      "union", len(set(g)|set(l0)|set(l1)))
r0 = rows(E1/"equiv_observations_lane0.jsonl")
r1 = rows(E1/"equiv_observations_lane1.jsonl")
print("obs: lane0", len(r0), "lane1", len(r1))
walls = {}
for r in r0:
    walls.setdefault(r["kernel"], []).append(r["wall_ms"]/1000)
med = {k: round(statistics.median(v)) for k, v in sorted(walls.items())}
print("lane0 kernel medians(s):", med)
plan = json.loads((E1/"lane_plan.json").read_text())
lane0_kernels = plan["lanes"][0]["kernels"]
done_all = set(g)|set(l0)
per = plan["per_kernel"]
# remaining per kernel needs survivor ids per kernel
surv = {}
for line in open(E1/"baseline_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if row.get("status") == "survived":
        surv.setdefault(row["kernel"], []).append(row["probe_id"])
rem = {k: len([p for p in surv[k] if p not in done_all]) for k in lane0_kernels}
rem = {k: v for k, v in rem.items() if v > 0}
print("lane0 remaining kernels:", len(rem), "probes:", sum(rem.values()))
print("remaining detail:", json.dumps(rem))
'''

c = _remote.connect()
sftp = c.open_sftp()
import io
sftp.putfo(io.BytesIO(REMOTE_SNAP.encode()), "/root/mk_v2/_e1_snap_remote.py")
sftp.close()
_remote.run(c, "date '+%F %T %z'; ps -eo pid,ppid,etime,args | awk '/run_e1_probe_study|_mutant_worker|e1_guard/ && !/awk/ {print $1, $2, $3, $NF}'", timeout=30)
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_e1_snap_remote.py", timeout=120)
_remote.run(c, "ls /root/mk_v2_runs/e1/EQUIV_DONE* 2>/dev/null; tail -n 2 /root/mk_v2_runs/e1_equiv_lane1.log", timeout=30)
c.close()
print("SNAP_DONE")
