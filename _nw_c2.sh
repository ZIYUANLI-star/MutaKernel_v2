cd /root/mk_v2
echo '=== EQUIV_ROUND_TIMEOUT_S / EQUIV_RUNS / EQUIV_BASE_SEED ==='
grep -n 'EQUIV_ROUND_TIMEOUT_S\|^EQUIV_RUNS\|^EQUIV_BASE_SEED\|BASELINE_PROTOCOL = ' -A 12 scripts/run_e1_probe_study.py | head -60
echo '=== policy_skip ==='
cat /root/mk_v2_runs/e1/cse_policy_skip.json
echo
echo '=== sparse_extreme policy ==='
grep -n 'sparse_extreme' -B 4 -A 30 src/stress/policy_bank.py | head -80
echo '=== signoff requeue obs: P37 records ==='
/root/miniconda3/bin/python - <<'PY'
import json
p='/root/mk_v2_runs/e1/cse_observations_lane3_signoff_requeue.jsonl'
for line in open(p):
    r=json.loads(line)
    print(r['probe_id'], r['outcome'], 'valid_rounds=',r.get('valid_rounds'),
          'wall_ms=',r.get('wall_ms'), 'timed_out=',r.get('timed_out'),
          'skipped=',r.get('skipped_policies'), 'planned=',r.get('stress_rounds_planned'),
          'witness=',r.get('witness_policy'),r.get('witness_round'),r.get('witness_seed'))
PY
echo '=== chain trigger / critical path alive? ==='
ls -la /root/mk_v2_runs/e1/SIGNOFF_ORCH_DONE 2>&1
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
tail -5 /root/mk_v2_runs/e3_b9_calib/chain_trigger.log 2>&1
