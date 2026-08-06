"""Did E1 equiv-phase trials exercise mode/dtype/config/repeated dimensions?"""
import _remote as R

py = r"""
import glob, json
from collections import Counter

modes = Counter()
dtypes = Counter()
round_types = Counter()
first_kill_cls = Counter()
witnessed = 0
files = sorted(glob.glob('/root/mk_v2_runs/e1/equiv_observations*.jsonl'))
print('files:', [f.split('/')[-1] for f in files])
for f in files:
    for line in open(f):
        if not line.strip():
            continue
        d = json.loads(line)
        for t in (d.get('trials') or []):
            case = t.get('case') or t
            modes[str(case.get('mode', t.get('mode', '?')))] += 1
            round_types[t.get('round_type')] += 1
            p = case.get('parameters') or {}
            dt = str(p.get('dtype', ''))
            if dt:
                dtypes[dt] += 1
print('trial modes:', dict(modes))
print('round types:', dict(round_types))
print('dtypes seen:', dict(dtypes))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_bp_dims.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _bp_dims.py",
      timeout=300)
c.close()
print("DIMS_CHECK_DONE")
