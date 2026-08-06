"""Peek at one unit's observation row structure."""
import _remote as R

peek_py = r"""
import json
p = '/root/mk_v2_runs/e3_b9_calib/units/L1_P1__float16/b9_L1_P1_observations.jsonl'
line = open(p).readline()
r = json.loads(line)
print(sorted(r.keys()))
print(json.dumps(r)[:700])
s = json.load(open(p.replace('observations.jsonl', 'summary.json')))
print('summary keys:', sorted(s.keys()))
print(json.dumps(s)[:700])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_b9_obs_peek.py", "w") as fh:
    fh.write(peek_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _b9_obs_peek.py",
      timeout=120)
c.close()
print("OBS_PEEK_DONE")
