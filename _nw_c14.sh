cd /root/mk_v2
echo '=== official aggregator ==='
/root/miniconda3/bin/python _cse_agg2.py 2>&1 | tail -40
echo '=== total LIKELY_EQUIVALENT universe ==='
/root/miniconda3/bin/python - <<'PY'
import json
n=0
for line in open('/root/mk_v2_runs/e1/equiv_observations.jsonl', encoding='utf-8'):
    r=json.loads(line)
    if r.get('evidence_grade')=='LIKELY_EQUIVALENT': n+=1
print('LIKELY_EQUIVALENT probes (CSE universe):', n)
PY
echo '=== signoff progress ==='
tail -3 /root/mk_v2_runs/signoff_orch.log
ls -la /root/mk_v2_runs/e1/SIGNOFF_ORCH_DONE 2>&1
tail -3 /root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness/review.log
