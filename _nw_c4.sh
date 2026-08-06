cd /root/mk_v2
/root/miniconda3/bin/python - <<'PY'
import json
p='/root/mk_v2_runs/e1/cse_observations_lane3_signoff_requeue.jsonl'
for line in open(p):
    r=json.loads(line)
    if r['probe_id']!='L1_P37__sync_remove__1': continue
    d=r['divergence']
    print('--- divergence ---')
    print(json.dumps({k:v for k,v in d.items() if k!='input_summary'}, indent=2)[:4000])
    print('--- input_summary ---')
    print(json.dumps(d.get('input_summary'), indent=2)[:2000])
    tr=r['trials']
    print('--- trial count', len(tr))
    for t in tr:
        if t.get('policy')=='sparse_extreme':
            print('sparse_extreme si=%s seed=%s status=%s reason=%s'%(t.get('sub_index'),t.get('seed'),t.get('status'),str(t.get('reason'))[:200]))
    print('--- last 3 trials ---')
    for t in tr[-3:]:
        print(t.get('round_type'),t.get('policy'),t.get('sub_index'),t.get('seed'),t.get('status'))
PY
echo '=== probe files / kernel source ==='
ls /root/mk_v2_runs/e1/probes | head
/root/miniconda3/bin/python - <<'PY'
import json,glob,os
for f in sorted(glob.glob('/root/mk_v2_runs/e1/probes/*.json')):
    d=json.load(open(f))
    k=d.get('kernel',{})
    if k.get('problem_name','').startswith('L1_P37'):
        print('FILE',f)
        print('kernel',k.get('problem_name'),k.get('level'),k.get('problem_id'))
        print('probes',[p['probe_id'] for p in d['probes']])
        src=d['kernel_source']
        print('--- kernel_source len',len(src))
        print(src)
        break
PY
