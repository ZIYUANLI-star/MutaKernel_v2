"""Deep probe: plan strategy composition, C6/M-dir/B-port readiness."""
import _remote as R

py = r"""
import json, os
from collections import Counter

camp = '/root/mk_v2_runs/e3_campaign'

print('=== plan structure ===')
plan = json.load(open(camp + '/wave1_lane_m_plan_v2.json'))
print('top keys:', list(plan.keys()))
# find case list
for k, v in plan.items():
    if isinstance(v, list) and v and isinstance(v[0], dict):
        print('list field:', k, 'len', len(v), 'sample keys:', list(v[0].keys()))
        sc = Counter(x.get('strategy_id') or x.get('strategy') for x in v)
        print('strategy split:', dict(sc))
        cc = Counter(x.get('corpus') or x.get('corpus_id') for x in v)
        print('corpus split:', dict(cc))
        break

print()
print('=== observations: strategy split so far ===')
sc = Counter(); corp = Counter()
with open(camp + '/lane_m_run/observations.jsonl') as f:
    for l in f:
        r = json.loads(l)
        sc[r.get('strategy_id') or r.get('strategy')] += 1
        s = r.get('subject_id') or ''
        corp[s.split('_')[0] if s else '?'] += 1
print('strategies:', dict(sc))

print()
print('=== e3_c6 / e3_corpora / e4_mdir_smoke contents ===')
for d in ['/root/mk_v2_runs/e3_c6', '/root/mk_v2_runs/e3_corpora',
          '/root/mk_v2_runs/e4_mdir_smoke']:
    print(d, ':')
    for dp, dn, fn in os.walk(d):
        for f in fn[:20]:
            print('  ', os.path.join(dp, f).replace(d, ''), 
                  os.path.getsize(os.path.join(dp, f)))
        break

print()
print('=== run_e3_external.py: which baselines supported ===')
src = open('/root/mk_v2/scripts/run_e3_external.py').read()
import re
for m in re.findall(r'(?:B\d+|b\d+|robust|kbenchx|kernelbenchx|sanitizer|fuzz|mdir|m_dir|m-dir)', src, re.I):
    pass
# simpler: argparse choices
for line in src.splitlines():
    ls = line.strip()
    if ('choices' in ls or 'add_argument' in ls or 'validator' in ls.lower()
            or 'baseline' in ls.lower()) and len(ls) < 150:
        print('  ', ls)

print()
print('=== build_mdir_strategy_row.py head ===')
src = open('/root/mk_v2/scripts/build_mdir_strategy_row.py').read()
print(src[:1500])

print()
print('=== run_ablation.py: argparse ===')
src = open('/root/mk_v2/scripts/run_ablation.py').read()
for line in src.splitlines():
    ls = line.strip()
    if 'add_argument' in ls and len(ls) < 150:
        print('  ', ls)

print()
print('=== b11_compute_sanitizer.py: argparse ===')
src = open('/root/mk_v2/scripts/b11_compute_sanitizer.py').read()
for line in src.splitlines():
    ls = line.strip()
    if 'add_argument' in ls and len(ls) < 150:
        print('  ', ls)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_chain_probe2.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _chain_probe2.py",
      timeout=600)
c.close()
print("PROBE2_DONE")
