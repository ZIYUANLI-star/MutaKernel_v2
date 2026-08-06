import _remote

PY = r'''
import json, os
base = "/root/mk_v2_runs/e1/"
# P95 state
for line in open(base + "equiv_observations.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("probe_id") == "L1_P95__relop_replace__5":
        print("P95 grade:", r.get("evidence_grade"), "| signoff:", bool(r.get("signoff")))
print("equiv_summary grades:", json.loads(open(base + "equiv_summary.json", encoding="utf-8").read())["grades"])
# skip config
raw = json.loads(open(base + "cse_policy_skip.json", encoding="utf-8").read())
print("skip map:", {k: v for k, v in raw["skip"].items()})
# archives
for fn in ("equiv_observations_signoff_archive.jsonl", "cse_observations_signoff_archive.jsonl"):
    p = base + fn
    n = sum(1 for l in open(p, encoding="utf-8") if l.strip()) if os.path.exists(p) else "MISSING"
    print(fn, "lines:", n)
# lane3 obs / completed
print("lane3 obs lines:", sum(1 for l in open(base + "cse_observations_lane3.jsonl", encoding="utf-8") if l.strip()))
print("lane3 completed:", len(json.loads(open(base + "cse_completed_lane3.json", encoding="utf-8").read())))
# bak timestamps
import glob, time
for p in sorted(glob.glob(base + "*bak_signoff*")) + sorted(glob.glob("/root/mk_v2/scripts/*.bak_signoff")):
    print("bak:", p, time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p))))
print("VERIFY_DONE")
'''
c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_signoff_verify_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _signoff_verify_remote.py", timeout=120)
print("== driver process & log ==")
_remote.run(c, "ps aux | grep 'signoff_[r]equeue' ; echo ---; "
               "ls -la /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log 2>/dev/null; "
               "tail -20 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log 2>/dev/null; echo ---; "
               "grep -n 'MK_CSE_ROUND_TIMEOUT' /root/mk_v2/scripts/run_e1_cse_falsify.py | head -3", timeout=120)
c.close()
