# -*- coding: utf-8 -*-
"""E1 baseline/equiv 独立复算(只读远端)+ E0 对照 INCONCLUSIVE 细分核查。"""
import _remote

SCRIPT = r'''
import json, collections

def load_obs(p):
    return [json.loads(l) for l in open(p) if l.strip()]

# ---- E0: trial-level reasons for the 8 corrected-INCONCLUSIVE controls ----
c5 = json.load(open('/root/mk_v2_runs/e0_run5_s0/original_controls.json'))
print('=== E0 corrected-INCONCLUSIVE control reasons ===')
for k, v in sorted(c5.items()):
    if v['corrected']['status'] == 'unknown':
        reasons = set()
        for t in (v['corrected'].get('trials') or []):
            reasons.add(t.get('reason','')[:90])
        print(' ', k, '|', '; '.join(sorted(reasons))[:220])

# ---- E1 baseline ----
b = load_obs('/root/mk_v2_runs/e1/baseline_observations.jsonl')
print()
print('=== E1 baseline_observations.jsonl ===')
print('rows:', len(b), 'unique probe_id:', len(set(o.get('probe_id') for o in b)))
print('keys:', sorted(b[0].keys()))
st = collections.Counter(o.get('status') for o in b)
print('status counts:', dict(st))
cats = collections.Counter(o.get('operator_category') for o in b)
print('probes by category:', dict(cats))

def bycat(pred):
    d = collections.Counter()
    for o in b:
        if pred(o):
            d[o.get('operator_category')] += 1
    return dict(d)

for s in st:
    print('status=%s by category:' % s, bycat(lambda o, s=s: o.get('status') == s))

# md5 for提交对账
import hashlib
h = hashlib.md5(open('/root/mk_v2_runs/e1/baseline_observations.jsonl','rb').read()).hexdigest()
print('baseline md5:', h)

# ---- E1 equiv ----
print()
print('=== E1 equiv_observations.jsonl ===')
e = load_obs('/root/mk_v2_runs/e1/equiv_observations.jsonl')
print('rows:', len(e), 'unique probe_id:', len(set(o.get('probe_id') for o in e)))
print('keys:', sorted(e[0].keys()))
for field in ('status','grade','equiv_grade','verdict','result'):
    vals = collections.Counter(o.get(field) for o in e if field in o)
    if vals:
        print('%s counts:' % field, dict(vals))
try:
    summ = json.load(open('/root/mk_v2_runs/e1/equiv_summary.json'))
    print('equiv_summary.json:', json.dumps(summ)[:1500])
except Exception as ex:
    print('equiv_summary read fail:', ex)

# ---- CSE 进度(只读,仅供汇报) ----
print()
print('=== CSE progress (read-only) ===')
graded = collections.Counter()
seen = set()
import glob
for p in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane*.jsonl')):
    if '.bak' in p: continue
    for o in load_obs(p):
        pid = o.get('probe_id')
        if pid in seen: continue
        seen.add(pid)
        graded[o.get('grade') or o.get('status')] += 1
print('graded unique:', len(seen), dict(graded))
'''

c = _remote.connect()
_remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300)
c.close()
