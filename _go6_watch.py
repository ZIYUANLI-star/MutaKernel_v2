#!/usr/bin/env python3
"""Post-deploy: full pytest regression, then watch until each lane finishes
one probe under the new pipeline (or 50 min timeout)."""
import json
import time

import _remote

c = _remote.connect()

print("=" * 12, "full pytest regression (CPU-only)")
code, o, e = _remote.run(
    c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python "
       "-m pytest tests -q 2>&1 | tail -4", timeout=1200, echo=False)
print(o.rstrip()[-800:])

BASE = {"3": 25, "4": 31}
done = {"3": False, "4": False}
t_end = time.time() + 50 * 60
while time.time() < t_end and not all(done.values()):
    time.sleep(90)
    status = []
    for lane in ("3", "4"):
        cmd = (f"wc -l < /root/mk_v2_runs/e1/cse_observations_lane{lane}.jsonl; "
               f"tail -1 /root/mk_v2_runs/e1/cse_observations_lane{lane}.jsonl | "
               "/root/miniconda3/bin/python -c \"import json,sys; "
               "r=json.loads(sys.stdin.readline()); "
               "print(json.dumps({k: r.get(k) for k in ('probe_id','outcome',"
               "'wall_ms','input_pipeline','valid_rounds')}))\"")
        _, o, _ = _remote.run(c, cmd, timeout=60, echo=False)
        lines = o.strip().splitlines()
        n = int(lines[0])
        status.append(f"lane{lane} obs={n}")
        if n > BASE[lane] and not done[lane]:
            done[lane] = True
            print(f"PROBE_DONE lane{lane}: {lines[1]}")
    # live cadence + memory
    _, o, _ = _remote.run(
        c, "ls /root/mk_v2_runs/e1/e1cse_*/res_*.json 2>/dev/null | head -4; "
           "cat /sys/fs/cgroup/memory.current 2>/dev/null; "
           "ps -eo pid,%cpu,rss,args | grep _mutant_worker.py | grep -v grep | "
           "awk '{print $1, $2, int($3/1048576)\"GB\"}'", timeout=60, echo=False)
    mem = o.strip().splitlines()
    print(time.strftime("%H:%M:%S"), " | ".join(status), "|", "; ".join(mem[-4:]))

# final: per-round timing sample of the first new probes
print("=" * 12, "new-probe trial timing sample")
cmd = ("""/root/miniconda3/bin/python -c "
import json
for lane in (3, 4):
    rows = [json.loads(l) for l in open(f'/root/mk_v2_runs/e1/cse_observations_lane{lane}.jsonl')]
    r = rows[-1]
    tr = r.get('trials') or []
    tot = sum((t.get('timings_ms') or {}).get('total_ms', 0) for t in tr)
    print(lane, r['probe_id'], r['outcome'], 'wall_s=%.0f' % (r['wall_ms']/1000),
          'rounds=', len(tr), 'in_round_s=%.0f' % (tot/1000),
          'pipeline=', r.get('input_pipeline'))
" """)
_, o, _ = _remote.run(c, cmd, timeout=60, echo=False)
print(o.strip())
c.close()
print("WATCH_DONE")
