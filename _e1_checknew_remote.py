"""Remote-side: print equiv observations appended after the restart."""
import json

rows = [json.loads(l) for l in open('/root/mk_v2_runs/e1/equiv_observations.jsonl')
        if l.strip()]
print('total', len(rows))
for r in rows[68:]:
    print(json.dumps({
        'probe_id': r['probe_id'], 'kernel': r['kernel'],
        'grade': r['evidence_grade'], 'status': r['validation_status'],
        'inconclusive_class': r.get('inconclusive_class'),
        'timed_out': r['timed_out'], 'wall_s': round(r['wall_ms'] / 1000),
        'valid_rounds': r.get('valid_rounds'),
        'round_timeouts': r.get('trials') and sum(
            1 for t in r['trials'] if t.get('round_timeout')),
        'evidence': r.get('evidence'),
    }))
