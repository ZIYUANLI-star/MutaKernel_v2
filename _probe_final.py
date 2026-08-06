import _remote

SCRIPT = r"""
import json, glob, collections

# 1) L1_P20__relop_replace__3 evidence
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane4.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] == 'L1_P20__relop_replace__3':
        ev = r.get('evidence') or {}
        print('P20 evidence:', json.dumps(ev)[:800])
        nonpass = [t for t in r['trials'] if t.get('status') != 'pass']
        for t in nonpass:
            print('  nonpass:', t.get('round_type'), t.get('policy'), t.get('status'),
                  str(t.get('reason'))[:120], 'round_timeout=', t.get('round_timeout'))
        break

# 2) which records own the non-pass stress rounds, by policy
own = collections.defaultdict(list)
for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane[0-5].jsonl')):
    lane = f.split('lane')[-1].split('.')[0]
    for ln in open(f):
        r = json.loads(ln)
        for t in (r.get('trials') or []):
            if t.get('round_type') == 'stress' and t.get('status') not in ('pass',):
                own[(t.get('policy'), t.get('status'))].append((lane, r['probe_id']))
for k, v in sorted(own.items(), key=lambda kv: str(kv[0])):
    ids = collections.Counter(x[1] for x in v)
    print('stress', k, 'n=', len(v), 'records:', dict(list(ids.items())[:8]))

# 3) obs counts now
for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane[0-5].jsonl')):
    print(f.split('/')[-1], sum(1 for _ in open(f)))
print('FINAL_DONE')
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1500])
print("== GPU util samples (10s) ==")
code, o, e = _remote.run(c, "for i in 1 2 3 4 5; do nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; sleep 2; done", timeout=60, echo=False)
print(o)
c.close()
