#!/usr/bin/env python3
"""Read-only final context: remaining counts, torch import cost, code lines."""
import _remote

c = _remote.connect()
CMDS = [
    ("lane3 log tail", "tail -3 /root/mk_v2_runs/e1_cse_lane3.log"),
    ("lane4 log tail", "tail -3 /root/mk_v2_runs/e1_cse_lane4.log"),
    ("lane3 head", "grep -m2 'targets' /root/mk_v2_runs/e1_cse_lane3.log | tail -1"),
    ("lane4 head", "grep -m2 'targets' /root/mk_v2_runs/e1_cse_lane4.log | tail -1"),
    ("completed counts",
     "for f in /root/mk_v2_runs/e1/cse_completed_lane*.json; do "
     "echo -n \"$f: \"; /root/miniconda3/bin/python -c "
     "\"import json,sys; print(len(json.load(open('$f'))))\"; done"),
    ("worker lines 575-585", "sed -n '575,585p' /root/mk_v2/scripts/_mutant_worker.py"),
    ("torch import time",
     "time /root/miniconda3/bin/python -c 'import torch' 2>&1"),
    ("lane plan kernels",
     "/root/miniconda3/bin/python -c \"import json; p=json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json')); "
     "[print(i, l.get('kernels'), l.get('note','')) for i,l in enumerate(p['lanes'])]\""),
]
for title, cmd in CMDS:
    print("=" * 12, title)
    code, o, e = _remote.run(c, cmd, timeout=180, echo=False)
    print(o.rstrip()[:3000])
    if e.strip():
        print("STDERR:", e.strip()[:600])
c.close()
print("DONE")
