import json, collections
recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/baseline_observations.jsonl') if l.strip()]
print('total observations:', len(recs))
st = collections.Counter(r.get('status') for r in recs)
print('overall:', dict(st.most_common()))

by_level = collections.defaultdict(collections.Counter)
for r in recs:
    lvl = (r.get('probe_id') or '').split('_')[0]
    by_level[lvl][r.get('status')] += 1
for lvl in sorted(by_level):
    print(lvl, dict(by_level[lvl].most_common()))

controls = json.load(open('/root/mk_v2_runs/e1/original_controls.json'))
cst = collections.Counter(v.get('status') for v in controls.values())
print('controls total:', len(controls), dict(cst))
bad = [(k, v.get('status'), v.get('reason_class')) for k, v in controls.items() if v.get('status') != 'survived']
for k, s, rc in sorted(bad):
    print('  ctrl-fail:', k, s, rc or '')

op = collections.defaultdict(collections.Counter)
for r in recs:
    pid = r.get('probe_id') or ''
    parts = pid.split('__')
    if len(parts) >= 2:
        op[parts[1]][r.get('status')] += 1
print('--- stillborn rate by operator (top) ---')
rows = []
for o, cnt in op.items():
    tot = sum(cnt.values())
    sb = cnt.get('stillborn', 0)
    if sb:
        rows.append((sb / tot, sb, tot, o))
for rate, sb, tot, o in sorted(rows, reverse=True)[:8]:
    print(f'  {o}: {sb}/{tot} ({rate:.0%})')
