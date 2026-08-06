import _remote

SCRIPT = r"""
import json
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] == 'L1_P35__sync_remove__0':
        nps = [t for t in (r.get('trials') or []) if t.get('status') != 'pass']
        print([(t.get('round_type'), t.get('policy'), t.get('status'),
                bool(t.get('round_timeout')), str(t.get('reason'))[:80]) for t in nps])

# lane4 remaining probes by kernel (plan kernels minus done)
import collections
done = collections.Counter()
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane4.jsonl'):
    done[json.loads(ln)['kernel']] += 1
print('lane4 done by kernel:', dict(done))
p = json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))
per_k = p['per_kernel']
l4 = [l for l in p['lanes'] if l['lane'] == 4][0]
for k in l4['kernels']:
    print(k, 'likely_probes=', per_k[k]['likely_probes'], 'done=', done.get(k, 0))
print('CHK4_DONE')
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1000])
c.close()
