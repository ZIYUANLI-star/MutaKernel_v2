"""Inspect the anomalous fp32 heavy-tail unit L1_P99__float32."""
import _remote as R

py = r"""
import glob, json
from collections import Counter
from pathlib import Path

OUT = Path('/root/mk_v2_runs/e3_b9_calib')
# final row
rows = []
for f in sorted(glob.glob(str(OUT / 'calibration*.jsonl'))):
    for line in open(f):
        if line.strip():
            r = json.loads(line)
            if r['unit'] == 'L1_P99__float32':
                rows.append(r)
rows.sort(key=lambda r: str(r.get('finished_at')))
r = rows[-1]
print('rows for unit:', len(rows))
print(json.dumps(r, indent=1))

# error values
d = OUT / 'units' / 'L1_P99__float32'
obs = list(d.glob('b9_*_observations.jsonl'))[0]
lines = [l for l in open(obs) if l.strip()]
vals = []
for l in lines[-int(r.get('cases') or 32):]:
    o = json.loads(l)
    e = (o.get('b9') or {}).get('max_abs_err')
    vals.append(e)
cnt = Counter(vals)
print('error value histogram:', dict(sorted(cnt.items())))
tol = r['calibrated_tol']
print('tol:', tol, 'max:', max(vals), 'max/tol:', max(vals)/tol if tol else None)
print('task_file:', r.get('task_file'))
# heavy tail? which values exceed tol
print('values > tol:', [v for v in vals if v > tol])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_b9_p99.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _b9_p99.py", timeout=120)
c.close()
print("P99_INSPECT_DONE")
