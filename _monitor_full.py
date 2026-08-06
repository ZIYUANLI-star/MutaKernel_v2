"""Full remote status sweep: processes, GPU, lane progress, guard, queues."""
import _remote

CMD1 = (
    "date -u '+UTC_NOW=%Y-%m-%d %H:%M:%S'; uptime; echo SEP; "
    "nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo SEP; "
    "ps aux | grep -E 'run_e1|mutant_worker|guard|falsify|probe_study|watch' | grep -v grep; echo SEP; "
    "ls -la /root/mk_v2_runs/ | tail -40"
)

CMD2 = (
    "for f in /root/mk_v2_runs/e1_cse_lane*.log; do echo \"== $f\"; tail -c 400 $f; echo; done; echo SEP; "
    "ls /root/mk_v2_runs/e1/ | head -60; echo SEP; "
    "wc -l /root/mk_v2_runs/e1/cse_observations_lane*.jsonl 2>/dev/null; echo SEP; "
    "cat /root/mk_v2_runs/e1/cse_lane_plan.json 2>/dev/null | head -c 2000; echo SEP; "
    "crontab -l 2>/dev/null; echo SEP; "
    "ls /root/mk_v2_runs/*.log 2>/dev/null | tail -20"
)

AGG = r"""
import json, glob
from collections import Counter

plan = {}
try:
    plan = json.load(open("/root/mk_v2_runs/e1/cse_lane_plan.json"))
except Exception as e:
    print("no lane plan:", e)

total = Counter()
done_ids = set()
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")):
    lane = path.rsplit("lane", 1)[-1].split(".")[0]
    grades = Counter()
    n = 0
    for l in open(path):
        if not l.strip():
            continue
        r = json.loads(l)
        g = r.get("outcome") or r.get("cse_grade") or r.get("grade") or "?"
        grades[g] += 1
        total[g] += 1
        done_ids.add(r.get("probe_id"))
        n += 1
    print(f"lane{lane}: n={n} {dict(grades)}")
print("TOTAL:", sum(total.values()), dict(total))

if isinstance(plan, dict):
    for k, v in plan.items():
        if isinstance(v, list):
            rem = [p for p in v if (p if isinstance(p, str) else p.get("probe_id")) not in done_ids]
            print(f"plan[{k}]: total={len(v)} remaining={len(rem)}")
print("AGG_DONE")
"""

c = _remote.connect()
print("##### PART1: system/processes #####")
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print("##### PART2: lanes/logs/queues #####")
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
print(o)
s = c.open_sftp()
with s.open("/root/mk_v2/_agg_now.py", "w") as f:
    f.write(AGG)
s.close()
print("##### PART3: progress aggregate #####")
_, o, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_agg_now.py 2>&1", timeout=240, echo=False)
c.close()
print(o)
print("MONITOR_DONE")
