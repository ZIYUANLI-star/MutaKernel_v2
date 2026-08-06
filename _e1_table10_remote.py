import json, collections
recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/baseline_observations.jsonl') if l.strip()]
cat = collections.defaultdict(collections.Counter)
for r in recs:
    cat[r.get('operator_category') or '?'][r.get('status')] += 1
print('=== Table10-style by operator category (baseline) ===')
for c in sorted(cat):
    d = cat[c]
    tot = sum(d.values())
    a = d['killed'] + d['survived']
    kr = 100 * d['killed'] / a if a else 0
    print(f"{c}: total={tot} killed={d['killed']} survived={d['survived']} "
          f"mpe={d['machine_proven_equivalent']} excluded={d['excluded_control_failed']} "
          f"stillborn={d['stillborn']} inconclusive={d['inconclusive_timeout']+d['unknown']+d['inconclusive_worker_failure']} "
          f"kill_rate_analyzable={kr:.1f}%")
print()
print('=== fault_class of survivors (top12) ===')
fc = collections.Counter(r.get('fault_class') for r in recs if r.get('status') == 'survived')
for k, v in fc.most_common(12):
    print(f'  {k}: {v}')
print('TABLE10_DONE')
