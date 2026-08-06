import json, collections
recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/equiv_observations.jsonl') if l.strip()]
print('total', len(recs))
print('grades:', dict(collections.Counter(r['evidence_grade'] for r in recs).most_common()))

inc = [r for r in recs if r['evidence_grade'] == 'INCONCLUSIVE']
print('\nINCONCLUSIVE:', len(inc))
print('classes:', dict(collections.Counter(str(r.get('inconclusive_class')) for r in inc).most_common()))
print('reasons:', dict(collections.Counter((r.get('reason') or '')[:90] for r in inc).most_common(6)))
print('timed_out:', dict(collections.Counter(str(r.get('timed_out')) for r in inc).most_common()))
print('by kernel:', dict(collections.Counter(r['kernel'] for r in inc).most_common(10)))

print('\nwall_ms percentiles (all recs):')
ws = sorted(r.get('wall_ms') or 0 for r in recs)
for q in (0.5, 0.9, 0.99):
    print(f'  p{int(q*100)}: {ws[int(q*(len(ws)-1))]/1000:.0f}s')

print('\nsequence of grades (index: grade, kernel) for idx 55..131:')
for i, r in enumerate(recs):
    if i >= 55:
        print(f'  {i}: {r["evidence_grade"][:12]:<12} {r["kernel"]:<8} {r["operator_name"]:<20} wall={int((r.get("wall_ms") or 0)/1000)}s to={r.get("timed_out")}')
print('DIAG3_DONE')
