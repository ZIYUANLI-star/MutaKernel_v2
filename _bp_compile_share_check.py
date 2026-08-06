"""Check for compile-time fields in E1 ledgers + within-tolerance round data."""
import _remote as R

py = r"""
import json

# equiv observation record fields
r = json.loads(open('/root/mk_v2_runs/e1/equiv_observations.jsonl').readline())
print('equiv obs keys:', sorted(r.keys()))
for k in sorted(r.keys()):
    if any(s in k.lower() for s in ('compile', 'time', 'wall', 'ms')):
        print(' ', k, ':', str(r[k])[:120])

# CSE trial rounds: do pass rounds carry error magnitudes?
r2 = json.loads(open('/root/mk_v2_runs/e1/cse_observations_lane1.jsonl').readline())
t = (r2.get('trials') or [])[:2]
print('cse trial sample:', json.dumps(t, indent=1)[:900])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_bp_cc.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _bp_cc.py",
      timeout=120)
c.close()
print("COMPILE_CHECK_DONE")
