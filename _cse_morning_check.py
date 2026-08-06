import _remote

AGG = r"""
import json
from collections import Counter

print("== per-lane CSE observations ==")
total = Counter()
by_lane = {}
import glob
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")):
    recs = [json.loads(l) for l in open(path) if l.strip()]
    lane = path.rsplit("lane", 1)[-1].split(".")[0]
    grades = Counter()
    for r in recs:
        g = r.get("cse_grade") or r.get("grade") or r.get("evidence_grade") or "?"
        grades[g] += 1
        total[g] += 1
    by_lane[lane] = (len(recs), dict(grades))
    print(f" lane{lane}: n={len(recs)} {dict(grades)}")
print("total:", sum(v[0] for v in by_lane.values()), dict(total))

print("\n== flips (falsified during CSE) ==")
flips = []
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")):
    for l in open(path):
        if not l.strip():
            continue
        r = json.loads(l)
        g = r.get("cse_grade") or r.get("grade") or r.get("evidence_grade") or ""
        if "NON_EQUIVALENT" in g or "WITNESSED" in g:
            flips.append(r)
print(f"flips: {len(flips)}")
fc = Counter(r.get("fault_class") for r in flips)
pol = Counter()
for r in flips:
    pol[r.get("witness_policy") or r.get("policy")] += 1
kc = Counter(r.get("kernel") for r in flips)
print(" by fault_class:", dict(fc.most_common()))
print(" by policy:", dict(pol.most_common()))
print(" by kernel:", dict(kc.most_common(10)))
for r in flips[:12]:
    print("  ", r.get("probe_id"))

print("\n== inconclusive detail ==")
inc = []
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")):
    for l in open(path):
        if not l.strip():
            continue
        r = json.loads(l)
        g = r.get("cse_grade") or r.get("grade") or r.get("evidence_grade") or ""
        if "INCONCLUSIVE" in g:
            inc.append((path.rsplit('/',1)[-1], r.get("probe_id"),
                        r.get("inconclusive_class"), r.get("timed_out")))
for x in inc[:15]:
    print(" ", x)
print("inconclusive total:", len(inc))
print("AGG_DONE")
"""

CMD_STATUS = (
    "cat /root/mk_v2_runs/cse_split_trigger.log; echo SEP; "
    "ps aux | grep 'run_e1_cse_[f]alsify' | grep -v grep | wc -l; "
    "ps aux | grep 'run_e1_cse_[f]alsify' | grep -o '\\-\\-lane [0-9]*'; echo SEP; "
    "for f in /root/mk_v2_runs/e1_cse_lane*.log; do echo \"== $f\"; tail -c 300 $f; echo; done; echo SEP; "
    "grep -ci 'out of memory\\|CUDA error\\|Traceback' /root/mk_v2_runs/e1_cse_lane*.log; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader"
)

c = _remote.connect()
s = c.open_sftp()
with s.open("/root/mk_v2/_cse_agg.py", "w") as f:
    f.write(AGG)
s.close()
_, out, _ = _remote.run(c, CMD_STATUS, timeout=120, echo=False)
print(out)
print("=====AGG=====")
_, out2, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_cse_agg.py 2>&1",
                         timeout=240, echo=False)
c.close()
print(out2)
