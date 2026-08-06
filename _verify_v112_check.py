# -*- coding: utf-8 -*-
"""v1.11 后复查(只读):equiv 收官数据零变动核验 + CSE 进度快照。"""
import _remote

SCRIPT = r'''
import json, collections, glob, hashlib, os

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

print('=== equiv 收官数据零变动核验 ===')
summ = json.load(open('/root/mk_v2_runs/e1/equiv_summary.json'))
print('equiv_summary grades:', summ['grades'], '| completed:', summ['completed'])
e = load('/root/mk_v2_runs/e1/equiv_observations.jsonl')
g = collections.Counter(o.get('evidence_grade') for o in e)
print('equiv_observations rows:', len(e), 'unique:', len(set(o['probe_id'] for o in e)), '| by grade:', dict(g))
h = hashlib.md5(open('/root/mk_v2_runs/e1/equiv_observations.jsonl','rb').read()).hexdigest()
print('equiv_observations md5:', h)
st = os.stat('/root/mk_v2_runs/e1/equiv_observations.jsonl')
print('mtime:', __import__('datetime').datetime.utcfromtimestamp(st.st_mtime).isoformat() + 'Z')
plan = json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))
total = 0
for k, v in plan.items():
    if k.startswith('lane') and isinstance(v, list):
        total += len(v)
print('lane_plan created_at:', plan.get('created_at'))

print()
print('=== CSE 进度快照(只读) ===')
for f in sorted(glob.glob('/root/mk_v2_runs/e1/CSE_DONE*')):
    print('done marker:', os.path.basename(f))
rows = []
per_lane = {}
for p in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane*.jsonl')):
    if '.bak' in p or 'timeout' in p or 'env_v1' in p:
        continue
    r = load(p)
    per_lane[os.path.basename(p)] = collections.Counter(o.get('validation_status') for o in r)
    rows += r
best = {}
for o in rows:
    best[o['probe_id']] = o
print('graded unique probes:', len(best), '/ 453')
print('by validation_status:', dict(collections.Counter(o.get('validation_status') for o in best.values())))
for name, cnt in per_lane.items():
    print(' ', name, dict(cnt))
fails = sorted(pid for pid, o in best.items() if o.get('validation_status') == 'fail')
print('FALSIFIED so far:', fails)
incs = sorted(pid for pid, o in best.items() if o.get('validation_status') == 'inconclusive')
print('INCONCLUSIVE so far:', incs)
'''

c = _remote.connect()
_remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300)
c.close()
