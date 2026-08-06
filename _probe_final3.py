import _remote

SCRIPT = r"""
import json
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] in ('L1_P35__const_perturb__4', 'L1_P35__relop_replace__7'):
        nps = [t for t in (r.get('trials') or []) if t.get('status') != 'pass']
        print(r['probe_id'], '->', [(t.get('round_type'), t.get('policy'), t.get('status'),
              bool(t.get('round_timeout')), str(t.get('reason'))[:80]) for t in nps])
        print('  evidence:', json.dumps(r.get('evidence') or {})[:300])
print('CHK_DONE')
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1000])
print("== GPU util samples ==")
code, o, e = _remote.run(c, "for i in 1 2 3 4 5 6 7 8; do nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader; sleep 2; done", timeout=60, echo=False)
print(o)
c.close()
