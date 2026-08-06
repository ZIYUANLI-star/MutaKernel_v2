import _remote

SCRIPT = r"""
import json
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] == 'L1_P94__const_perturb__7':
        d = r['divergence']
        print('policy/sub/seed:', d.get('policy'), d.get('sub_index'), d.get('seed'), '| detail:', d.get('detail'))
        print('input_summary:', json.dumps(d.get('input_summary'))[:300])
        print('oracle:', json.dumps(d.get('oracle'))[:600])
        print('errors:', d.get('errors'))
        nonpass = [t for t in (r.get('trials') or []) if t.get('status') not in ('pass', 'fail')]
        print('nonpass trials:', [(t.get('policy'), t.get('status'), str(t.get('reason'))[:60]) for t in nonpass])
        break
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:800])
c.close()
