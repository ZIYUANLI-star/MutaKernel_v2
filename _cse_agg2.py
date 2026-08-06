import _remote

AGG = r"""
import glob
import json
from collections import Counter

first = json.loads(open("/root/mk_v2_runs/e1/cse_observations_lane1.jsonl").readline())
print("record keys:", sorted(first.keys()))

grade_key = None
for k in ("cse_grade", "grade", "verdict", "result", "status", "evidence_grade", "outcome"):
    if k in first:
        grade_key = k
        break
print("using grade key:", grade_key)

total = Counter()
flips, inc = [], []
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")):
    recs = [json.loads(l) for l in open(path) if l.strip()]
    grades = Counter(str(r.get(grade_key)) for r in recs)
    total.update(grades)
    lane = path.rsplit("lane", 1)[-1].split(".")[0]
    print(f" lane{lane}: n={len(recs)} {dict(grades)}")
    for r in recs:
        g = str(r.get(grade_key))
        if "FALSIF" in g or "NON_EQ" in g:
            flips.append(r)
        elif "INCONCLUSIVE" in g:
            inc.append(r)
print("TOTAL:", sum(total.values()), dict(total))

print("\nFLIPS:", len(flips))
for r in flips:
    print(json.dumps({k: r.get(k) for k in ("probe_id", "kernel", "fault_class",
          "operator_name", "witness_policy", "policy", "witness_round")},
          ensure_ascii=False))

print("\nINCONCLUSIVE:", len(inc))
for r in inc[:10]:
    print(" ", r.get("probe_id"), r.get("inconclusive_class"), r.get("timed_out"))

# wall time stats per lane for ETA
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")):
    recs = [json.loads(l) for l in open(path) if l.strip()]
    walls = sorted(r.get("wall_ms", 0) / 1000 for r in recs)
    if walls:
        lane = path.rsplit("lane", 1)[-1].split(".")[0]
        print(f"lane{lane} wall_s: median={walls[len(walls)//2]:.0f} "
              f"p90={walls[int(len(walls)*0.9)]:.0f} max={walls[-1]:.0f}")
print("AGG2_DONE")
"""

c = _remote.connect()
s = c.open_sftp()
with s.open("/root/mk_v2/_cse_agg2.py", "w") as f:
    f.write(AGG)
s.close()
_, out, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_cse_agg2.py 2>&1",
                        timeout=240, echo=False)
c.close()
print(out)
