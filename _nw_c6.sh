cd /root/mk_v2
grep -n 'WORKER_CORRECTED\|WORKER_LEGACY\|^WORKER' scripts/run_e1_probe_study.py | head
echo '=== problem file ==='
cat /root/mk_v2/KernelBench/KernelBench/level1/37_FrobeniusNorm_.py
echo '=== sync_remove__1 vs __0 mutated diff vs original ==='
/root/miniconda3/bin/python - <<'PY'
import json,difflib
d=json.load(open('/root/mk_v2_runs/e1/probes/L1_P37.json'))
src=d['kernel_source'].splitlines()
for p in d['probes']:
    if p['probe_id'] in ('L1_P37__sync_remove__0','L1_P37__sync_remove__1'):
        print('=====',p['probe_id'],'operator',p['operator_name'],'fault',p.get('fault_class'))
        print('site',json.dumps(p.get('site'),ensure_ascii=False)[:300])
        print('desc',p.get('description'))
        m=p['mutated_code'].splitlines()
        print('\n'.join(l for l in difflib.unified_diff(src,m,lineterm='',n=3) if l.startswith(('+','-','@'))))
PY
