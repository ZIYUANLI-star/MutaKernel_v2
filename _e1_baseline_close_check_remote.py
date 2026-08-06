import json, collections, hashlib

OBS = '/root/mk_v2_runs/e1/baseline_observations.jsonl'
SUM = '/root/mk_v2_runs/e1/baseline_summary.json'

data = open(OBS, 'rb').read()
print('obs_md5', hashlib.md5(data).hexdigest(), 'bytes', len(data))
rows = [json.loads(l) for l in data.decode().splitlines() if l.strip()]
ids = [r['probe_id'] for r in rows]
print('rows', len(rows), 'unique', len(set(ids)))
tab = collections.defaultdict(collections.Counter)
for r in rows:
    tab[r['operator_category']][r['status']] += 1
for c in sorted(tab):
    print('CAT', c, 'probes', sum(tab[c].values()), json.dumps(dict(tab[c]), sort_keys=True))
tot = collections.Counter(r['status'] for r in rows)
print('OVERALL', json.dumps(dict(tot), sort_keys=True))
sdata = open(SUM, 'rb').read()
print('summary_md5', hashlib.md5(sdata).hexdigest())
print('SUMMARY', sdata.decode())
print('CHECK_DONE')
