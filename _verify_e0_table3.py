# -*- coding: utf-8 -*-
"""E0 Table 3 独立复算(只读远端):run5 + run4 复用配对合并。"""
import _remote

SCRIPT = r'''
import json, math, collections

def load_obs(p):
    return [json.loads(l) for l in open(p) if l.strip()]

r5 = load_obs('/root/mk_v2_runs/e0_run5_s0/observations.jsonl')
r4 = load_obs('/root/mk_v2_runs/e0_run4_s0/observations.jsonl')
c5 = json.load(open('/root/mk_v2_runs/e0_run5_s0/original_controls.json'))

ids5 = set(o['probe_id'] for o in r5)
merged = r5 + [o for o in r4 if o['probe_id'] not in ids5]
print('merged total', len(merged))

def stratum(o):
    key = (o['level'], o['reference_stateful'])
    return {(1,False):'L1-stateless',(1,True):'L1-stateful',(2,True):'L2-stateful'}[key]

def wilson(k, n, z=1.959963984540054):
    if n == 0: return (0.0, 1.0)
    p = k/n
    d = 1 + z*z/n
    ctr = (p + z*z/(2*n))/d
    hw = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (max(0,ctr-hw), min(1,ctr+hw))

rows = collections.defaultdict(lambda: dict(sampled=0, ctrl=0, analyz=0, flips=0, inc=0))
sec_flips = collections.Counter()
sec_n = 0
for o in merged:
    s = stratum(o)
    rows[s]['sampled'] += 1
    if not o['original_control_ok']:
        continue
    rows[s]['ctrl'] += 1
    cst = o['corrected']['status']
    lst = o['legacy']['status']
    if cst not in ('killed','survived') or lst not in ('killed','survived'):
        rows[s]['inc'] += 1
        print('  excluded control-passing probe:', o['probe_id'], s, 'legacy=', lst, 'corrected=', cst)
        continue
    rows[s]['analyz'] += 1
    if lst != cst:
        rows[s]['flips'] += 1
        print('  FLIP:', o['probe_id'], s, 'legacy=', lst, '-> corrected=', cst, 'flip_paired flag=', o['flip_paired'])
    sec_n += 1
    h = o['historical_status']
    if h in ('killed','survived') and cst != h:
        sec_flips[(h, cst)] += 1

tot = dict(sampled=0, ctrl=0, analyz=0, flips=0, inc=0)
print()
print('=== Table 3 recompute ===')
for s in ['L1-stateless','L1-stateful','L2-stateful']:
    r = rows[s]
    for k in tot: tot[k] += r[k]
    lo, hi = wilson(r['flips'], r['analyz'])
    rate = 100.0*r['flips']/max(r['analyz'],1)
    print('%s: sampled=%d controls_passed=%d analyzable=%d flips=%d rate=%.1f%% CI=[%.1f,%.1f] excluded_inc=%d'
          % (s, r['sampled'], r['ctrl'], r['analyz'], r['flips'], rate, 100*lo, 100*hi, r['inc']))
lo, hi = wilson(tot['flips'], tot['analyz'])
print('Overall: sampled=%d controls_passed=%d analyzable=%d flips=%d rate=%.1f%% CI=[%.1f,%.1f] excluded_inc=%d'
      % (tot['sampled'], tot['ctrl'], tot['analyz'], tot['flips'],
         100.0*tot['flips']/tot['analyz'], 100*lo, 100*hi, tot['inc']))
print()
print('secondary vs historical: n=', sec_n, 'flips=', sum(sec_flips.values()), dict(sec_flips))
print()
print('=== run5 original controls (%d kernels) ===' % len(c5))
lk = {k:v for k,v in c5.items() if v['legacy']['status']=='killed'}
print('legacy killed originals:', len(lk), '/', len(c5))
cc = collections.Counter(v['corrected']['status'] for v in lk.values())
print('corrected verdicts on those:', dict(cc))
lvl = collections.Counter(('L2' if k.startswith('L2') else 'L1') for k in lk)
lvl_all = collections.Counter(('L2' if k.startswith('L2') else 'L1') for k in c5)
print('legacy-killed by level:', dict(lvl), 'of totals', dict(lvl_all))
other = {k:v for k,v in c5.items() if v['legacy']['status']!='killed' and v['corrected']['status'] not in ('killed','survived')}
print('legacy-passed but corrected non-definitive:', len(other))
for k,v in sorted(other.items()):
    err = v['corrected'].get('error','')
    print('   ', k, v['legacy']['status'], '->', v['corrected']['status'], '|', str(err)[:110])
for k,v in sorted(lk.items()):
    if v['corrected']['status'] not in ('killed','survived'):
        print('  legacy-killed, corrected non-definitive:', k, v['corrected']['status'], '|', str(v['corrected'].get('error',''))[:110])
'''

c = _remote.connect()
_remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300)
c.close()
