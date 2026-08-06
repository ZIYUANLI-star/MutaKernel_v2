#!/usr/bin/env python3
"""Deploy phase 2: kill drivers first, then workers; verify ledger; wait for
guard AUTORESTART; verify new drivers + v2 manifests."""
import time

import _remote

c = _remote.connect()
r = lambda cmd, t=120: _remote.run(c, cmd, timeout=t)

print("### 1. current pids")
r("pgrep -af 'run_e1_cse_falsify.py.*--lane [35]'")
r("pgrep -af 'scripts/_mutant_worker.py'")

print("### 2. kill drivers first")
r("pkill -TERM -f 'run_e1_cse_falsify.py.*--lane 3$' ; "
  "pkill -TERM -f 'run_e1_cse_falsify.py.*--lane 5$' ; sleep 2; "
  "pgrep -af 'run_e1_cse_falsify' || echo DRIVERS_DEAD")
r("pgrep -f 'run_e1_cse_falsify.py.*--lane' >/dev/null && "
  "pkill -9 -f 'run_e1_cse_falsify.py.*--lane' ; sleep 1; "
  "pgrep -af 'run_e1_cse_falsify' || echo DRIVERS_DEAD_CONFIRMED")

print("### 3. kill workers")
r("pkill -9 -f 'scripts/_mutant_worker.py' ; sleep 2; "
  "pgrep -af 'scripts/_mutant_worker.py' || echo WORKERS_DEAD")

print("### 4. post-kill ledger check")
r("wc -l /root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
  "/root/mk_v2_runs/e1/cse_observations_lane5.jsonl")
r("md5sum /root/mk_v2_runs/e1/cse_completed_lane3.json "
  "/root/mk_v2_runs/e1/cse_completed_lane5.json")
r("for p in L1_P46__relop_replace__0 L1_P23__init_modify__0; do "
  "echo -n \"$p in active ledgers: \"; "
  "grep -l $p /root/mk_v2_runs/e1/cse_completed_lane3.json "
  "/root/mk_v2_runs/e1/cse_completed_lane5.json "
  "/root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
  "/root/mk_v2_runs/e1/cse_observations_lane5.jsonl 2>/dev/null || echo NONE; "
  "done")

print("### 5. wait for guard AUTORESTART (cycle <=120s)")
time.sleep(140)
r("pgrep -af 'run_e1_cse_falsify.py.*--lane [35]' || echo NOT_YET")
r("tail -n 4 /root/mk_v2_runs/e1_cse_lane3.log; echo ---; "
  "tail -n 4 /root/mk_v2_runs/e1_cse_lane5.log")
c.close()
print("DEPLOY_PHASE2_DONE")
