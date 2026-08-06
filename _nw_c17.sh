cd /root/mk_v2
echo '=== deduped ledger (post P46) ==='
/root/miniconda3/bin/python - <<'PY'
import glob, json, collections
files = sorted(p for p in glob.glob("/root/mk_v2_runs/e1/cse_observations_lane*.jsonl")
               if ".bak" not in p)
recs = {}
for p in files:
    for line in open(p, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            recs[r["probe_id"]] = r
universe = sum(1 for line in open('/root/mk_v2_runs/e1/equiv_observations.jsonl', encoding='utf-8')
               if json.loads(line).get('evidence_grade') == 'LIKELY_EQUIVALENT')
c = collections.Counter(r.get("outcome") for r in recs.values())
print("CSE universe (LIKELY_EQUIVALENT probes):", universe)
print("graded probes:", len(recs), " outcomes:", dict(c))
print("ungraded:", universe - len(recs))
print()
fals = sorted(p for p, r in recs.items() if r.get("outcome") == "FALSIFIED")
print("FALSIFIED =", len(fals))
for p in fals:
    r = recs[p]
    print("   %-32s %-16s policy=%-22s si=%-2s seed=%s" % (
        p, r.get("operator_name"), r.get("witness_policy"),
        r.get("witness_round"), r.get("witness_seed")))
print()
kern = collections.Counter(recs[p]["kernel"] for p in fals)
print("FALSIFIED per kernel:", dict(kern))
PY
echo
echo '=== sparse_extreme round tally across all P37 evidence ==='
/root/miniconda3/bin/python - <<'PY'
import json, glob
tot = fail = 0
print("production sign-off requeue:")
for line in open('/root/mk_v2_runs/e1/cse_observations_lane3_signoff_requeue.jsonl', encoding='utf-8'):
    r = json.loads(line)
    if not r['probe_id'].startswith('L1_P37'):
        continue
    rows = [t for t in (r.get('trials') or []) if t.get('policy') == 'sparse_extreme']
    f = sum(1 for t in rows if t.get('status') != 'pass')
    tot += len(rows); fail += f
    print("   %-34s %d rounds, %d fail" % (r['probe_id'], len(rows), f))
print("review:")
R = '/root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness'
s = json.load(open(R + '/review_summary.json'))
for g in ('control', 'witness', 'lateral'):
    n = sum(len(rep['rounds']) for rep in s['groups'][g])
    f = sum(1 for rep in s['groups'][g] for r in rep['rounds'] if r['status'] != 'pass')
    tot += n; fail += f
    print("   %-34s %d rounds, %d fail" % (g, n, f))
print("TOTAL sparse_extreme rounds on L1_P37: %d, divergences: %d (%.1f%%)"
      % (tot, fail, 100.0 * fail / tot))
PY
echo
echo '=== B9 state now ==='
tail -6 /root/mk_v2_runs/e3_b9_calib/chain_trigger.log
ls /root/mk_v2_runs/e3_b9_calib/CHAIN_TRIGGER_FIRED 2>&1
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
