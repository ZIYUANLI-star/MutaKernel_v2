import json, collections

def load(p):
    try:
        return [json.loads(l) for l in open(p) if l.strip()]
    except FileNotFoundError:
        return []

base = load('/root/mk_v2_runs/e1/equiv_observations.jsonl')
l0 = load('/root/mk_v2_runs/e1/equiv_observations_lane0.jsonl')
l1 = load('/root/mk_v2_runs/e1/equiv_observations_lane1.jsonl')
print(f'counts: pre-switch={len(base)} lane0={len(l0)} lane1={len(l1)} total={len(base)+len(l0)+len(l1)}')

allr = base + l0 + l1
print('grades all:', dict(collections.Counter(r['evidence_grade'] for r in allr).most_common()))
for name, rs in (('lane0', l0), ('lane1', l1)):
    if rs:
        ws = sorted(r.get('wall_ms', 0) for r in rs)
        med = ws[len(ws)//2] / 1000
        gr = dict(collections.Counter(r['evidence_grade'] for r in rs).most_common())
        to = sum(1 for r in rs if r.get('timed_out'))
        pe = sum(1 for r in rs if (r.get('evidence') or {}).get('budget_exhausted'))
        print(f'{name}: {gr} median_wall={med:.0f}s timed_out={to} budget_exhausted_graded={pe}')
        kern = collections.Counter(r['kernel'] for r in rs)
        print(f'  kernels touched: {dict(kern.most_common(6))}')

wit = [r for r in allr if r['evidence_grade'] == 'WITNESSED_NON_EQUIVALENT']
print('\nwitnessed non-eq so far:', len(wit))
print(' by fault_class:', dict(collections.Counter(r.get('fault_class') for r in wit).most_common()))
print(' by policy:', dict(collections.Counter(((r.get('divergence') or {}).get('policy')) for r in wit).most_common(8)))
print('AGG_DONE')
