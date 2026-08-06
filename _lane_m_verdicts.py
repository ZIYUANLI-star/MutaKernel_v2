"""Lane M verdict distribution + per-case cost stats."""
import _remote as R

py = r"""
import glob, json
from collections import Counter

rows = []
for f in glob.glob('/root/mk_v2_runs/e3_campaign/**/observations.jsonl',
                   recursive=True):
    for line in open(f):
        if line.strip():
            rows.append(json.loads(line))
vc = Counter()
walls = []
for r in rows:
    wr = r.get('worker_result') or {}
    v = wr.get('status') or wr.get('verdict')
    if isinstance(v, dict):
        v = v.get('status')
    vc[str((r.get('validation_status'), v))] += 1
    w = r.get('parent_wall_ms')
    if w:
        walls.append(w / 1000.0)
print('n =', len(rows))
print('verdicts:', dict(vc.most_common()))
walls.sort()
if walls:
    print('case wall s: median %.1f  p95 %.1f  mean %.1f' %
          (walls[len(walls)//2], walls[int(len(walls)*0.95)],
           sum(walls)/len(walls)))
ds = Counter(r.get('dataset') for r in rows)
print('by dataset:', dict(ds))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_lm_v.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _lm_v.py",
      timeout=180)
c.close()
print("VERDICTS_DONE")
