import json, collections
recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/baseline_observations.jsonl') if l.strip()]
print('total', len(recs))
print(collections.Counter(r.get('status') for r in recs))
for r in recs:
    if r.get('status') in ('unknown', 'stillborn'):
        print('---', r.get('probe_id'), r.get('status'))
        err = r.get('error') or r.get('error_message') or ''
        print('   err:', str(err)[:300])
excl = collections.Counter(r.get('problem_name') for r in recs if r.get('status') == 'excluded_control_failed')
print('excluded by problem:', dict(excl))
