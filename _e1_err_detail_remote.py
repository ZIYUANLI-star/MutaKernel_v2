import json
recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/baseline_observations.jsonl') if l.strip()]
targets = ['L1_P23__acc_downgrade__0', 'L1_P22__cast_remove__0', 'L1_P20__const_perturb__2']
for r in recs:
    if r.get('probe_id') in targets:
        err = str(r.get('error') or r.get('error_message') or '')
        # print the tail where the actual nvcc error message lives
        print('=====', r['probe_id'])
        print(err[-1500:])
        print()
