"""Inspect the exact records to be amended and the review evidence."""
import _remote

PY = r'''
import json, glob, os

TARGETS = {
    "L1_P46__index_replace__5",
    "L1_P37__arith_replace__14",
    "L1_P37__sync_remove__1",
    "L1_P37__sync_remove__0",
    "L1_P37__launch_config_mutate__0",
    "L1_P37__epsilon_modify__0",
}
MAIN = ["cse_observations_lane0.jsonl", "cse_observations_lane1.jsonl",
        "cse_observations_lane2.jsonl", "cse_observations_lane3.jsonl",
        "cse_observations_lane4.jsonl", "cse_observations_lane5.jsonl",
        "cse_observations_lane3_p96_5400.jsonl",
        "cse_observations_lane3_final_requeue.jsonl",
        "cse_observations_lane5_final_requeue.jsonl"]
base = "/root/mk_v2_runs/e1/"
for fn in MAIN:
    with open(base + fn, encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            pid = r.get("probe_id")
            if pid in TARGETS:
                keys = sorted(r.keys())
                print(f"--- {fn}:{i} {pid}")
                print("    keys:", keys)
                for k in ("outcome", "grade", "witness", "rounds_completed",
                          "rounds_planned", "random_pass", "stress_pass",
                          "n_random", "n_stress", "fault_class", "tag",
                          "opt_tag", "kernel", "problem_name"):
                    if k in r:
                        v = json.dumps(r[k], ensure_ascii=False)
                        print(f"    {k} = {v[:400]}")
print("=== P95 equiv record ===")
with open(base + "equiv_observations.jsonl", encoding="utf-8") as f:
    for i, line in enumerate(f):
        r = json.loads(line)
        if r.get("probe_id") == "L1_P95__relop_replace__5":
            print(f"line {i} keys:", sorted(r.keys()))
            print(json.dumps(r, ensure_ascii=False)[:2000])
print("=== review dirs ===")
for d in sorted(glob.glob(base + "final_window_review/*")):
    for root, _, files in os.walk(d):
        for fn2 in files:
            p = os.path.join(root, fn2)
            print(p, os.path.getsize(p))
print("=== summaries ===")
for p in sorted(glob.glob(base + "*summary*.json")) + sorted(glob.glob(base + "final_window*")):
    if os.path.isfile(p):
        print("##", p)
        print(open(p, encoding="utf-8").read()[:1500])
print("INSPECT2_DONE")
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_signoff_inspect2_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _signoff_inspect2_remote.py",
            timeout=300)
c.close()
