#!/usr/bin/env python3
"""Read-only: P35 witness detail + current progress snapshot."""
import _remote

c = _remote.connect()
cmd = ("""/root/miniconda3/bin/python -c "
import json
rows = [json.loads(l) for l in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl')]
r = [x for x in rows if x['probe_id'] == 'L1_P35__arith_replace__16'][-1]
print(json.dumps({k: r.get(k) for k in ('probe_id','kernel','outcome',
    'witness_policy','witness_round','witness_seed','valid_rounds','wall_ms',
    'input_pipeline','validation_status')}, indent=1))
d = r.get('divergence') or {}
print('divergence detail:', d.get('detail'), '| oracle keys:', list((d.get('oracle') or {}).keys())[:6])
" """)
_remote.run(c, cmd, timeout=60)
_remote.run(c, "tail -2 /root/mk_v2_runs/e1_cse_lane3.log; tail -2 /root/mk_v2_runs/e1_cse_lane4.log", timeout=60)
c.close()
