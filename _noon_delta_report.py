"""Delta report: new observations since lever activation, per-strategy split."""
import _remote as R

py = r"""
import json, os, time
from collections import Counter

f = '/root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl'
rows = [json.loads(l) for l in open(f) if l.strip()]
print('total obs:', len(rows), ' newest age s:',
      int(time.time() - os.path.getmtime(f)))

# per-strategy x verdict
mat = Counter()
for r in rows:
    mat[(r.get('strategy_name'), r.get('validation_status'))] += 1
strats = sorted(set(k[0] for k in mat))
print('%-28s %6s %6s %6s' % ('strategy', 'pass', 'fail', 'inc'))
for s in strats:
    print('%-28s %6d %6d %6d' % (s, mat[(s, 'pass')], mat[(s, 'fail')],
                                 mat[(s, 'inconclusive')]))

# subject-level: subjects with >=1 fail under any strategy
subj_fail = set()
subj_all = set()
for r in rows:
    subj_all.add(r['subject_id'])
    if r.get('validation_status') == 'fail':
        subj_fail.add(r['subject_id'])
print('subjects touched:', len(subj_all),
      ' subjects with >=1 fail:', len(subj_fail),
      ' (%.1f%%)' % (100.0 * len(subj_fail) / max(1, len(subj_all))))

# subjects where B1u anchor (five-iid) itself fails vs only stress strategies
anchor_fail = set()
for r in rows:
    if r.get('strategy_name') == 'five-iid-historical-anchor' \
            and r.get('validation_status') == 'fail':
        anchor_fail.add(r['subject_id'])
only_stress = subj_fail - anchor_fail
print('anchor(B1u)-failing subjects:', len(anchor_fail),
      ' stress-only-failing subjects:', len(only_stress))

# throughput in the last hour via file growth: count obs per strategy replicate
# order field ~ schedule position; use last-100 wall
walls = [r.get('parent_wall_ms', 0) / 1000.0 for r in rows[-100:]]
walls.sort()
print('last-100 wall s median: %.1f' % walls[len(walls)//2])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_noon_delta.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _noon_delta.py",
      timeout=180)
c.close()
print("NOON_DELTA_DONE")
