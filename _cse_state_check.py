import _remote

REMOTE_PY = r"""
import glob
import json

print("== files ==")
import subprocess
for f in sorted(glob.glob("/root/mk_v2_runs/e1/cse_*")):
    print(" ", f)

print("== new lane3/4/5 records ==")
for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane[345].jsonl")):
    for l in open(path):
        r = json.loads(l)
        print(f" {path[-11:]} {r['probe_id'][:40]:<40} {r['outcome']:<24} "
              f"wall={r.get('wall_ms',0)/1000:.0f}s valid={r.get('valid_rounds')} "
              f"ntrials={len(r.get('trials') or [])}")
print("STATE_DONE")
"""

c = _remote.connect()
s = c.open_sftp()
with s.open("/root/mk_v2/_cse_state.py", "w") as f:
    f.write(REMOTE_PY)
s.close()
_, out, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_cse_state.py 2>&1; "
                        "echo LOGSEP; head -3 /root/mk_v2_runs/e1_cse_lane3.log; "
                        "grep -h 'GUARD_STARTED\\|banner\\|targets' /root/mk_v2_runs/e1_cse_lane3.log | tail -4",
                        timeout=300, echo=False)
c.close()
print(out)
