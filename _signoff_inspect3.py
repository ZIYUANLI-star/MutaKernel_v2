"""Inspect grading criterion and per-record round evidence."""
import _remote

PY = r'''
import json

base = "/root/mk_v2_runs/e1/"
TARGETS = ["L1_P46__index_replace__5", "L1_P37__arith_replace__14",
           "L1_P37__sync_remove__1", "L1_P37__sync_remove__0",
           "L1_P37__launch_config_mutate__0", "L1_P37__epsilon_modify__0"]
with open(base + "cse_observations_lane3.jsonl", encoding="utf-8") as f:
    recs = {json.loads(l)["probe_id"]: json.loads(l) for l in f}
for pid in TARGETS:
    r = recs[pid]
    trials = r.get("trials") or []
    from collections import Counter
    st = Counter(t.get("status") for t in trials) if isinstance(trials, list) else "N/A"
    phases = Counter(t.get("phase") for t in trials) if isinstance(trials, list) else "N/A"
    print(f"== {pid}")
    print("  outcome:", r["outcome"], "| valid_rounds:", r.get("valid_rounds"),
          "| timed_out:", r.get("timed_out"), "| wall_ms:", r.get("wall_ms"))
    print("  witness:", r.get("witness_policy"), r.get("witness_round"), r.get("witness_seed"))
    print("  trial statuses:", dict(st))
    print("  trial phases:", dict(phases))
    if isinstance(trials, list):
        bad = [t for t in trials if t.get("status") not in ("pass", "passed", "ok")]
        for t in bad[:8]:
            print("   nonpass:", json.dumps({k: t.get(k) for k in
                  ("round", "phase", "policy", "sub_index", "seed", "status", "reason")},
                  ensure_ascii=False)[:300])
    print("  input_pipeline:", r.get("input_pipeline"))

print()
print("=== review_summary files ===")
for d in ("p46_index_replace_5", "p37_cluster", "p95_relop_replace_5"):
    p = base + "final_window_review/" + d + "/review_summary.json"
    print("##", p)
    print(open(p, encoding="utf-8").read())

print("=== grade function ===")
import re
src = open("/root/mk_v2/scripts/run_e1_cse_falsify.py", encoding="utf-8").read()
m = re.search(r"def grade_cse_evidence.*?(?=\ndef |\nclass |\Z)", src, re.S)
print(m.group(0)[:4000] if m else "NOT FOUND grade_cse_evidence")
print("INSPECT3_DONE")
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_signoff_inspect3_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _signoff_inspect3_remote.py",
            timeout=300)
c.close()
