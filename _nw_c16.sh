R=/root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness
echo '=== full review log ==='
cat $R/review.log
echo
echo '=== control_rep3 divergence detail ==='
/root/miniconda3/bin/python - <<'PY'
import json
R='/root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness'
d=json.load(open(R+'/control_rep3_result.json'))
res=d['result']
div=res['divergence']
print('verdict', d['verdict'], 'wall_ms', d['wall_ms'])
print(json.dumps({k:v for k,v in div.items() if k!='input_summary'}, indent=2)[:2500])
print('input_summary', json.dumps(div.get('input_summary'), indent=2)[:900])
print()
print('=== per-rep round table ===')
s=json.load(open(R+'/review_summary.json'))
for g in ('control','witness','lateral'):
    for rep in s['groups'][g]:
        print('%-9s %-14s verdict=%-9s wall=%7.1fs rounds=%s' % (
            g, rep['name'], rep['verdict'], rep['wall_ms']/1000.0,
            [(r['sub_index'], r['seed'], r['status'], r['max_abs_error']) for r in rep['rounds']]))
print()
print('code:', s['recommendation_code'])
print('control_clean:', s['control_clean'], 'lateral_clean:', s['lateral_clean'],
      'witness_repro:', s['witness_reproductions_at_witness_round'])
print('elapsed_s:', s['elapsed_s'])
PY
echo
echo '=== ls review dir ==='
ls -la $R
echo '=== B9 chain trigger log tail ==='
tail -25 /root/mk_v2_runs/e3_b9_calib/chain_trigger.log
echo '=== signoff orch tail ==='
tail -12 /root/mk_v2_runs/signoff_orch.log
