"""Evening sweep: signoff completion, orchestrator actions, B9 wave status."""
import _remote

CMD1 = (
    "date '+LOCAL_NOW=%F %T %z'; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo SEP; "
    "ps aux | grep -E 'run_e1|mutant_worker|falsify|signoff|b9|sentinel|guard' | grep -v grep; echo SEP; "
    "tail -c 2500 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log; echo SEP; "
    "tail -c 3000 /root/mk_v2_runs/signoff_orch.log; echo SEP; "
    "ls -la /root/mk_v2_runs/e1/SIGNOFF_ORCH_DONE /root/mk_v2_runs/e1/signoff_orch_summary.json 2>/dev/null; "
    "cat /root/mk_v2_runs/e1/signoff_orch_summary.json 2>/dev/null; echo SEP; "
    "tail -c 2000 /root/mk_v2_runs/e3_b9_calib/chain_trigger.log; echo SEP; "
    "ls -la /root/mk_v2_runs/e3_b9_calib/ | grep -iE 'FIRED|EXIT|PAUSED|resume|queue_state'; "
    "cat /root/mk_v2_runs/e3_b9_calib/queue_state.json 2>/dev/null | head -c 1200"
)

CMD2 = (
    "for f in /root/mk_v2_runs/e3_b9_calib/lane*.log; do echo \"== $f\"; tail -c 600 $f; echo; done; echo SEP; "
    "wc -l /root/mk_v2_runs/e3_b9_calib/calibration_lane*.jsonl 2>/dev/null; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/completed_lane*.json 2>/dev/null; echo SEP; "
    "tail -c 800 /root/mk_v2_runs/e3_b9_calib/guard_b9.log 2>/dev/null; "
    "ls /root/mk_v2_runs/e3_b9_calib/*.log"
)

AGG = r"""
import json, glob
from collections import Counter
total = Counter()
per = {}
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")):
    if ".bak" in path:
        continue
    n = 0
    grades = Counter()
    for l in open(path):
        if not l.strip():
            continue
        r = json.loads(l)
        g = r.get("outcome") or "?"
        grades[g] += 1
        total[g] += 1
        n += 1
    per[path.rsplit("/",1)[-1]] = (n, dict(grades))
for k, v in per.items():
    print(k, v)
print("TOTAL:", sum(total.values()), dict(total))

# signoff six probes current grades
EXPECT = ["L1_P46__index_replace__5","L1_P37__arith_replace__14","L1_P37__sync_remove__1",
          "L1_P37__sync_remove__0","L1_P37__launch_config_mutate__0","L1_P37__epsilon_modify__0"]
found = {}
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")):
    if ".bak" in path:
        continue
    for l in open(path):
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get("probe_id") in EXPECT:
            found[r["probe_id"]] = (path.rsplit("/",1)[-1], r.get("outcome"),
                                     r.get("witness_policy"), r.get("rounds_completed"),
                                     round((r.get("wall_ms") or 0)/1000))
for p in EXPECT:
    print("SIGNOFF", p, found.get(p))
print("AGG_DONE")
"""

c = _remote.connect()
print("##### PART1 #####")
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print("##### PART2: B9 lanes #####")
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
print(o)
s = c.open_sftp()
with s.open("/root/mk_v2/_agg_now2.py", "w") as f:
    f.write(AGG)
s.close()
print("##### PART3: CSE ledger #####")
_, o, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_agg_now2.py 2>&1", timeout=240, echo=False)
c.close()
print(o)
print("MONITOR4_DONE")
