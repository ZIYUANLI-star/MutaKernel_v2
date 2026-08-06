#!/usr/bin/env python3
"""Post-deploy watch: reset peak counter once (--reset), then sample."""
import sys

import _remote

c = _remote.connect()
r = lambda cmd, t=120: _remote.run(c, cmd, timeout=t)

if "--reset" in sys.argv:
    r("echo 0 > /sys/fs/cgroup/memory/memory.max_usage_in_bytes && "
      "echo PEAK_RESET")

r("date '+%F %T %z'; free -g | sed -n 2p")
r("for f in memory.usage_in_bytes memory.max_usage_in_bytes; do "
  "v=$(cat /sys/fs/cgroup/memory/$f); "
  "echo \"$f $((v/1073741824)) GiB\"; done; "
  "grep oom_kill /sys/fs/cgroup/memory/memory.oom_control")
r("for p in $(pgrep -f 'scripts/_mutant_worker.py'); do "
  "cfg=$(tr '\\0' ' ' < /proc/$p/cmdline | sed 's/.*cfg_//;s/\\.json.*//'); "
  "hwm=$(awk '/VmHWM/{print int($2/1048576)}' /proc/$p/status); "
  "rss=$(awk '/VmRSS/{print int($2/1048576)}' /proc/$p/status); "
  "et=$(ps -o etimes= -p $p); "
  "echo \"worker $p $cfg elapsed=${et}s HWM=${hwm}GB RSS=${rss}GB\"; done")
r("tail -n 2 /root/mk_v2_runs/e1/cse_observations_lane3.jsonl | "
  "/root/miniconda3/bin/python -c \"import json,sys; "
  "[print('lane3:', (lambda r: (r['probe_id'], r['outcome'], "
  "round(r['wall_ms']/1000), r.get('input_pipeline'), r['finished_at']))"
  "(json.loads(l))) for l in sys.stdin]\"")
r("tail -n 2 /root/mk_v2_runs/e1/cse_observations_lane5.jsonl | "
  "/root/miniconda3/bin/python -c \"import json,sys; "
  "[print('lane5:', (lambda r: (r['probe_id'], r['outcome'], "
  "round(r['wall_ms']/1000), r.get('input_pipeline'), r['finished_at']))"
  "(json.loads(l))) for l in sys.stdin]\"")
r("wc -l /root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
  "/root/mk_v2_runs/e1/cse_observations_lane5.jsonl | head -2")
c.close()
print("WATCH_DONE")
