import json, collections

recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/baseline_observations.jsonl') if l.strip()]
completed = json.load(open('/root/mk_v2_runs/e1/baseline_completed.json'))
controls = json.load(open('/root/mk_v2_runs/e1/original_controls.json'))

ids = [r.get('probe_id') for r in recs]
print('INTEGRITY: observations=%d checkpoint=%d unique_ids=%d dup=%d' % (
    len(recs), len(completed), len(set(ids)), len(ids) - len(set(ids))))
missing = set(completed) - set(ids)
print('INTEGRITY: checkpoint ids missing from observations:', len(missing))

st = collections.Counter(r.get('status') for r in recs)
print('\nOVERALL:', dict(st.most_common()))
analyzable = st['killed'] + st['survived']
print('kill rate among analyzable: %d/%d = %.1f%%' % (st['killed'], analyzable, 100*st['killed']/analyzable))

by_level = collections.defaultdict(collections.Counter)
for r in recs:
    by_level[(r.get('probe_id') or '').split('_')[0]][r.get('status')] += 1
for lvl in sorted(by_level):
    c = by_level[lvl]
    a = c['killed'] + c['survived']
    kr = 100*c['killed']/a if a else 0
    print(f'{lvl}: {dict(c.most_common())}  kill_rate={kr:.1f}%')

print('\nCONTROLS: total=%d' % len(controls))
cc = collections.Counter(v.get('status') for v in controls.values())
print(' status:', dict(cc))
rc = collections.Counter((v.get('status'), v.get('reason_class')) for v in controls.values() if v.get('status') != 'survived')
for k, n in rc.most_common():
    print('  fail:', k, n)

print('\nBY OPERATOR (kill rate among analyzable, stillborn rate):')
op = collections.defaultdict(collections.Counter)
for r in recs:
    parts = (r.get('probe_id') or '').split('__')
    if len(parts) >= 2:
        op[parts[1]][r.get('status')] += 1
for o in sorted(op):
    c = op[o]
    tot = sum(c.values())
    a = c['killed'] + c['survived']
    kr = 100*c['killed']/a if a else 0
    print(f'  {o}: total={tot} killed={c["killed"]} survived={c["survived"]} '
          f'stillborn={c["stillborn"]} kill_rate={kr:.0f}%')

surv_by_kernel = collections.Counter((r.get('probe_id') or '').split('__')[0]
                                     for r in recs if r.get('status') == 'survived')
print('\nSURVIVORS: total=%d across %d kernels; top10:' % (sum(surv_by_kernel.values()), len(surv_by_kernel)))
for k, n in surv_by_kernel.most_common(10):
    print(f'  {k}: {n}')
print('ANALYSIS_DONE')
