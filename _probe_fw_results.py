import _remote

SCRIPT = r"""
import json, glob
for f in ['/root/mk_v2_runs/e1/cse_observations_lane3_p96_5400.jsonl',
          '/root/mk_v2_runs/e1/cse_observations_lane3_final_requeue.jsonl',
          '/root/mk_v2_runs/e1/cse_observations_lane5_final_requeue.jsonl']:
    for ln in open(f):
        r = json.loads(ln)
        trials = r.get('trials') or []
        rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
        sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
        np_ = sum(1 for t in trials if t.get('status') != 'pass')
        print(json.dumps({'probe_id': r['probe_id'], 'outcome': r['outcome'], 'rand': rp, 'stress': sp,
            'nonpass': np_, 'valid': r.get('valid_rounds'), 'to': r.get('timed_out'),
            'wall_s': round((r.get('wall_ms') or 0)/1000, 1), 'fin': r.get('finished_at'),
            'pipe': r.get('input_pipeline'), 'skipped': r.get('skipped_policies')}))
print('--- RECOMMENDATIONS ---')
for d in ['p46_index_replace_5', 'p37_cluster', 'p95_relop_replace_5']:
    print(f'== {d} ==')
    print(open(f'/root/mk_v2_runs/e1/final_window_review/{d}/RECOMMENDATION.txt').read())
print('--- final_window_summary ---')
print(open('/root/mk_v2_runs/e1/final_window_summary.json').read()[:2500])
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:800])
c.close()
