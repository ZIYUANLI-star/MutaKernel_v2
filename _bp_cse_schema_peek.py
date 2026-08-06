"""Peek CSE record schema for bitwise/tolerance-conforming evidence."""
import _remote as R

py = r"""
import json
f = '/root/mk_v2_runs/e1/cse_observations_lane1.jsonl'
r = json.loads(open(f).readline())
print(sorted(r.keys()))
for k in ('divergence', 'near_miss', 'max_abs', 'bitwise', 'valid_rounds',
          'trials', 'evidence'):
    if k in r:
        print(k, ':', json.dumps(r[k])[:220])
# scan all records for any field name containing 'bit' or 'diverg' or 'near'
import glob
names = set()
for f in glob.glob('/root/mk_v2_runs/e1/cse_observations*.jsonl'):
    for line in open(f):
        if line.strip():
            d = json.loads(line)
            for k in d:
                if any(s in k.lower() for s in ('bit', 'diverg', 'near', 'tol')):
                    names.add(k)
            break
print('interesting fields across files:', sorted(names))
# count records with nonzero divergence info among non-falsified
import collections
cnt = collections.Counter()
for f in glob.glob('/root/mk_v2_runs/e1/cse_observations_lane*.jsonl'):
    for line in open(f):
        if not line.strip():
            continue
        d = json.loads(line)
        div = d.get('divergence')
        if d.get('outcome') == 'STILL_LIKELY_EQUIVALENT' and div:
            cnt['sle_with_divergence'] += 1
        elif d.get('outcome') == 'STILL_LIKELY_EQUIVALENT':
            cnt['sle_clean'] += 1
print(dict(cnt))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_bp_cse_sp.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _bp_cse_sp.py",
      timeout=180)
c.close()
print("SCHEMA_PEEK_DONE")
