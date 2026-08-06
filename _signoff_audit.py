"""Audit the ledger after the two-actor overlap: check for double writes."""
import _remote

PY = r'''
import json, glob, os
base = "/root/mk_v2_runs/e1/"

print("=== P95 records in equiv ledger ===")
n = 0
for line in open(base + "equiv_observations.jsonl", encoding="utf-8"):
    if not line.strip():
        continue
    r = json.loads(line)
    if r.get("probe_id") == "L1_P95__relop_replace__5":
        n += 1
        print("grade:", r.get("evidence_grade"), "| status:", r.get("validation_status"))
        print("signoff keys:", [k for k in r if "signoff" in k or k == "witness"])
        print(json.dumps({k: r[k] for k in r if "signoff" in k}, ensure_ascii=False)[:600])
print("P95 record count:", n)
total = sum(1 for l in open(base + "equiv_observations.jsonl", encoding="utf-8") if l.strip())
print("equiv total lines:", total)

print()
print("=== archives and backups ===")
for p in sorted(glob.glob(base + "*signoff*")) + sorted(glob.glob(base + "*.bak_signoff")):
    print(p, os.path.getsize(p))
for p in sorted(glob.glob(base + "*signoff*.jsonl")):
    cnt = sum(1 for l in open(p, encoding="utf-8") if l.strip())
    print("  lines:", p, cnt)

print()
print("=== equiv_summary.json ===")
print(open(base + "equiv_summary.json", encoding="utf-8").read()[:1200])

print()
print("=== lane3 ledger ===")
cnt = sum(1 for l in open(base + "cse_observations_lane3.jsonl", encoding="utf-8") if l.strip())
comp = json.loads(open(base + "cse_completed_lane3.json", encoding="utf-8").read())
print("lane3 obs lines:", cnt, "| completed ids:", len(comp))
for pid in ("L1_P46__index_replace__5", "L1_P37__arith_replace__14"):
    print(pid, "in completed:", pid in comp)

print()
print("=== policy skip ===")
cfg = json.loads(open(base + "cse_policy_skip.json", encoding="utf-8").read())
print("skip keys:", {k: v for k, v in cfg.get("skip", {}).items()})
print("extra keys:", [k for k in cfg if k not in ("skip",)])

print()
print("=== signoff manifest (theirs) ===")
for p in sorted(glob.glob(base + "*manifest*signoff*")) + sorted(glob.glob(base + "signoff*")):
    if os.path.isfile(p):
        print("##", p)
        print(open(p, encoding="utf-8").read()[:800])

print()
print("=== rerun progress ===")
os.system("tail -6 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log")
t = base + "cse_observations_lane3_signoff_requeue.jsonl"
if os.path.exists(t):
    for l in open(t, encoding="utf-8"):
        r = json.loads(l)
        print("done:", r["probe_id"], r.get("outcome"))
print("AUDIT_DONE")
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_signoff_audit_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _signoff_audit_remote.py",
            timeout=300)
c.close()
