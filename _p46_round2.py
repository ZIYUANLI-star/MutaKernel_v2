import _remote

PY = r'''
import json, glob, os, time
base = "/root/mk_v2_runs/e1/"

print("=== orchestrator log (tail) ===")
os.system("tail -12 /root/mk_v2_runs/signoff_orch.log")

print()
print("=== round-2 tagged results ===")
p = base + "cse_observations_lane3_signoff_rerun2.jsonl"
if os.path.exists(p):
    for line in open(p, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            print(f"{r['probe_id']} {r.get('outcome')} valid_rounds={r.get('valid_rounds')} "
                  f"wall={round((r.get('wall_ms') or 0)/1000)}s")
else:
    print("not written yet (probe still running)")

print()
print("=== in-flight partial evidence ===")
dirs = sorted(glob.glob(base + "e1cse_*"), key=os.path.getmtime, reverse=True)[:2]
for d in dirs:
    for f in sorted(glob.glob(d + "/res_*.json")):
        age = time.time() - os.path.getmtime(f)
        try:
            r = json.load(open(f, encoding="utf-8"))
        except Exception as exc:
            print(f"{os.path.basename(f)}: unreadable ({type(exc).__name__})")
            continue
        trials = r.get("trials") or []
        rand = [t for t in trials if not t.get("policy")]
        stress = [t for t in trials if t.get("policy")]
        npass = sum(1 for t in trials if t.get("status") in ("pass", "passed", "ok"))
        print(f"{os.path.basename(f)} (updated {age:.0f}s ago)")
        print(f"  trials={len(trials)} random={len(rand)} stress={len(stress)} "
              f"pass={npass} valid_rounds={r.get('valid_rounds')}")
        if stress:
            print(f"  last stress policy: {stress[-1].get('policy')} "
                  f"status={stress[-1].get('status')}")

print()
print("=== resources ===")
os.system("grep oom_kill /sys/fs/cgroup/memory.events")
os.system("nvidia-smi --query-gpu=memory.used --format=csv,noheader")
os.system("ps -o pid,etime,cmd -C python 2>/dev/null | grep -E '_mutant_worker|_signoff_orch' "
          "| head -4")
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_p46_round2_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python -u /root/mk_v2/_p46_round2_remote.py", timeout=120)
c.close()
