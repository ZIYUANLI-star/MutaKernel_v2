import json, collections
recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/equiv_observations.jsonl') if l.strip()]
print('total', len(recs))
print('keys of first record:', sorted(recs[0].keys()))
print(json.dumps(recs[0], ensure_ascii=False)[:1200])
print()
for field in ('equiv_grade', 'verdict', 'outcome', 'label', 'result'):
    vals = collections.Counter(str(r.get(field)) for r in recs)
    if set(vals) != {'None'}:
        print(field, dict(vals.most_common()))
print('--- last record ---')
print(json.dumps(recs[-1], ensure_ascii=False)[:1200])
print('DIAG2_DONE')
