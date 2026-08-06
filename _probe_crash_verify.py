import _remote

SCRIPT = r"""
import json
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] == 'L1_P46__index_replace__5':
        d = r['divergence']
        print('DIVERGENCE:')
        print(json.dumps(d, indent=1)[:2500])
        trials = r.get('trials') or []
        print()
        print('last 4 trials:')
        for t in trials[-4:]:
            t2 = {k: v for k, v in t.items() if k not in ('timings_ms',)}
            print(json.dumps(t2)[:700])
        print()
        print('witness fields:', r.get('witness_policy'), r.get('witness_round'), r.get('witness_seed'))
        nonpass = [t for t in trials if t.get('status') not in ('pass', 'fail')]
        print('nonpass(non-fail) trials:', [(t.get('policy'), t.get('status'), str(t.get('reason'))[:60]) for t in nonpass])
        break
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1000])
c.close()
