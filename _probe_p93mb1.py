import _remote

SCRIPT = r"""
import json
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] == 'L1_P93__mask_boundary__1':
        trials = r.get('trials') or []
        rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
        sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
        print(json.dumps({'probe_id': r['probe_id'], 'outcome': r['outcome'], 'rand': rp, 'stress': sp,
            'valid': r.get('valid_rounds'), 'to': r.get('timed_out'),
            'wall_s': round((r.get('wall_ms') or 0)/1000, 1), 'fin': r.get('finished_at'),
            'pipe': r.get('input_pipeline')}))
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
c.close()
