import json, collections
recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/baseline_observations.jsonl') if l.strip()]
per = collections.defaultdict(collections.Counter)
for r in recs:
    pid = r.get('probe_id') or ''
    prob = pid.split('__')[0]
    per[prob][r.get('status')] += 1
for prob in ('L1_P19', 'L1_P20', 'L1_P22', 'L1_P23', 'L1_P24'):
    print(prob, dict(per[prob]))
