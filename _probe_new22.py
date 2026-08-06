import _remote

SCRIPT = r"""
import json, datetime
CUT = datetime.datetime.fromisoformat('2026-07-29T15:25:00+00:00')  # 23:25 CST
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    fin = datetime.datetime.fromisoformat(r['finished_at'])
    if fin >= CUT:
        trials = r.get('trials') or []
        rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
        sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
        np_ = sum(1 for t in trials if t.get('status') not in ('pass',))
        print(json.dumps({'probe_id': r['probe_id'], 'outcome': r['outcome'], 'rand': rp, 'stress': sp,
            'nonpass': np_, 'valid': r.get('valid_rounds'), 'to': r.get('timed_out'),
            'wall_s': round((r.get('wall_ms') or 0)/1000, 1), 'fin': r.get('finished_at'),
            'pipe': r.get('input_pipeline')}))
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:800])
c.close()
