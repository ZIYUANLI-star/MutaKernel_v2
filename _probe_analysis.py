import _remote

SCRIPT = r"""
import json, glob, statistics, datetime, collections

def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    i = min(len(xs) - 1, int(round(q * (len(xs) - 1))))
    return xs[i]

lanes = {}
for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane[0-5].jsonl')):
    lane = f.split('lane')[-1].split('.')[0]
    recs = []
    for ln in open(f):
        ln = ln.strip()
        if ln:
            recs.append(json.loads(ln))
    lanes[lane] = recs

print('== OUTCOME DIST ==')
tot = collections.Counter()
for lane, recs in lanes.items():
    c = collections.Counter(r['outcome'] for r in recs)
    tot.update(c)
    print(f'lane{lane}: n={len(recs)}', dict(c))
print('TOTAL:', sum(tot.values()), dict(tot))

print()
print('== FALSIFIED / WITNESSED LIST ==')
for lane, recs in lanes.items():
    for r in recs:
        if r['outcome'] in ('FALSIFIED', 'WITNESSED_NON_EQUIVALENT'):
            d = r.get('divergence') or {}
            n_trials = len(r.get('trials') or [])
            print(json.dumps({
                'lane': lane, 'probe_id': r['probe_id'], 'fault_class': r.get('fault_class'),
                'outcome': r['outcome'],
                'witness_policy': d.get('policy'), 'witness_round_type': d.get('round_type'),
                'witness_sub_index': d.get('sub_index'), 'witness_seed': d.get('seed'),
                'witness_detail': d.get('detail'),
                'trials_before_hit': n_trials, 'wall_s': round((r.get('wall_ms') or 0)/1000, 1),
                'has_witness': bool(d),
                'finished_at': r.get('finished_at'),
            }, ensure_ascii=False))

print()
print('== INCONCLUSIVE LIST ==')
for lane, recs in lanes.items():
    for r in recs:
        if r['outcome'] == 'INCONCLUSIVE':
            print(json.dumps({
                'lane': lane, 'probe_id': r['probe_id'],
                'class': r.get('inconclusive_class'),
                'timed_out': r.get('timed_out'), 'valid_rounds': r.get('valid_rounds'),
                'wall_s': round((r.get('wall_ms') or 0)/1000, 1),
                'finished_at': r.get('finished_at'),
            }))

print()
print('== P53 RECORDS (lane3) ==')
for r in lanes.get('3', []):
    if r.get('kernel') == 'L1_P53':
        trials = r.get('trials') or []
        st = collections.Counter(t.get('status') for t in trials)
        pols = sorted(set(t.get('policy') for t in trials if t.get('round_type') == 'stress' and t.get('policy')))
        skipped = {'mixed_extremes', 'sparse', 'sparse_extreme'} & set(pols)
        print(json.dumps({
            'probe_id': r['probe_id'], 'outcome': r['outcome'],
            'trial_status': dict(st), 'n_stress_policies': len(pols),
            'skipped_policies_present': sorted(skipped),
            'wall_s': round((r.get('wall_ms') or 0)/1000, 1),
            'finished_at': r.get('finished_at'),
        }))

print()
print('== WALL STATS (per lane, all outcomes) ==')
for lane, recs in lanes.items():
    walls = [(r.get('wall_ms') or 0)/1000 for r in recs]
    to = sum(1 for r in recs if r.get('timed_out'))
    if walls:
        print(f'lane{lane}: n={len(walls)} median={statistics.median(walls):.0f}s p95={pct(walls,0.95):.0f}s max={max(walls):.0f}s timed_out={to}')

print()
print('== GRADING CONSISTENCY ==')
bad_still, bad_fals = [], []
for lane, recs in lanes.items():
    for r in recs:
        trials = r.get('trials') or []
        rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
        sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
        if r['outcome'] == 'STILL_LIKELY_EQUIVALENT' and (rp < 40 or sp < 42):
            bad_still.append((lane, r['probe_id'], rp, sp, r.get('valid_rounds'), r.get('validation_status')))
        if r['outcome'] in ('FALSIFIED', 'WITNESSED_NON_EQUIVALENT') and not r.get('divergence'):
            bad_fals.append((lane, r['probe_id']))
print('STILL_LIKELY below 40rand+42stress threshold:', len(bad_still))
for b in bad_still[:20]:
    print('  ', b)
print('FALSIFIED missing witness:', len(bad_fals), bad_fals)

print()
print('== RANDOM/STRESS PASS RATES + PER-POLICY ==')
rnd = collections.Counter(); strs = collections.Counter()
pol = collections.defaultdict(collections.Counter)
for lane, recs in lanes.items():
    for r in recs:
        for t in (r.get('trials') or []):
            if t.get('round_type') == 'random':
                rnd[t.get('status')] += 1
            elif t.get('round_type') == 'stress':
                strs[t.get('status')] += 1
                pol[t.get('policy')][t.get('status')] += 1
print('random rounds:', dict(rnd))
print('stress rounds:', dict(strs))
print('per-policy stress status:')
for p in sorted(pol):
    print(f'  {p}: {dict(pol[p])}')

print()
print('== THROUGHPUT last 12h / 24h (finished_at) ==')
now = datetime.datetime.now(datetime.timezone.utc)
for lane in ('3', '4', '5'):
    recs = lanes.get(lane, [])
    ts = []
    for r in recs:
        fa = r.get('finished_at')
        if fa:
            ts.append(datetime.datetime.fromisoformat(fa))
    n12 = sum(1 for t in ts if (now - t).total_seconds() <= 12*3600)
    n24 = sum(1 for t in ts if (now - t).total_seconds() <= 24*3600)
    walls12 = [(r.get('wall_ms') or 0)/1000 for r in recs
               if r.get('finished_at') and (now - datetime.datetime.fromisoformat(r['finished_at'])).total_seconds() <= 12*3600]
    med12 = statistics.median(walls12) if walls12 else None
    print(f'lane{lane}: last12h={n12} last24h={n24} wall_median_12h={med12 and round(med12)}s last_finish={max(ts).isoformat() if ts else None}')

print()
print('== LANE PLAN SIZES ==')
p = json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))
ls = p.get('lanes')
if isinstance(ls, list):
    for i, l in enumerate(ls):
        if isinstance(l, list):
            print(f'lane{i}: planned={len(l)}')
        else:
            print(f'lane{i}:', str(l)[:200])

print()
print('== DEDUP / CROSS-LANE PROBE OVERLAP ==')
seen = collections.defaultdict(list)
for lane, recs in lanes.items():
    for r in recs:
        seen[r['probe_id']].append(lane)
dups = {k: v for k, v in seen.items() if len(v) > 1}
print('unique probes graded:', len(seen), 'duplicated across lanes:', len(dups))
for k, v in list(dups.items())[:10]:
    print('  ', k, v)
print('ANALYSIS_DONE')
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:2000])
c.close()
