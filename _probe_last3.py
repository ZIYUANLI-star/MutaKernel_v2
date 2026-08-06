import _remote

SCRIPT = r"""
import json, datetime
CUT = datetime.datetime.fromisoformat('2026-07-30T01:40:00+00:00')
recs = []
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if datetime.datetime.fromisoformat(r['finished_at']) >= CUT:
        trials = r.get('trials') or []
        rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
        sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
        np_ = sum(1 for t in trials if t.get('status') != 'pass')
        print(json.dumps({'probe_id': r['probe_id'], 'outcome': r['outcome'], 'rand': rp, 'stress': sp,
            'nonpass': np_, 'valid': r.get('valid_rounds'), 'to': r.get('timed_out'),
            'wall_s': round((r.get('wall_ms') or 0)/1000, 1), 'fin': r.get('finished_at'),
            'pipe': r.get('input_pipeline')}))

# archive content check
print('--- inc_archive ---')
for ln in open('/root/mk_v2_runs/e1/cse_observations_inc_archive_v2.jsonl'):
    r = json.loads(ln)
    print(r['probe_id'], r['outcome'], r.get('inconclusive_class'))

# final lane3 tally (post-archive) + full outcome dist
import glob, collections
tot = collections.Counter()
for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane[0-5].jsonl')):
    c = collections.Counter(json.loads(ln)['outcome'] for ln in open(f))
    tot.update(c)
    print(f.split('/')[-1], dict(c))
print('TOTAL(post-step2a-archive):', sum(tot.values()), dict(tot))
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:800])
c.close()
