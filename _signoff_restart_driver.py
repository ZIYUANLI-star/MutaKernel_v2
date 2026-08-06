"""Restart the signoff_requeue driver so the round-timeout patch takes effect."""
import time

import _remote

ENV = ("PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
       "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
       "MK_GPU_MEMORY_FRACTION=0.92 MK_CSE_ROUND_TIMEOUT=600")
LAUNCH = (
    "cd /root/mk_v2 && " + ENV +
    " nohup /root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py"
    " --out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench"
    " --timeout 5400 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json"
    " --lane 3 --lane-tag signoff_requeue"
    " >> /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log 2>&1 & echo RELAUNCHED $!"
)

c = _remote.connect()
print("== verify patch is on disk ==")
_remote.run(c, "grep -c 'MK_CSE_ROUND_TIMEOUT' /root/mk_v2/scripts/run_e1_cse_falsify.py",
            timeout=60)
print("== kill old (unpatched) driver + workers ==")
_remote.run(c, (
    "pkill -f 'run_e1_cse_falsify.py.*signoff_requeue' ; sleep 3; "
    "pkill -f '_mutant_worker.py' ; sleep 2; "
    "ps aux | grep -E 'falsify|_mutant_worker' | grep -v grep | wc -l"
), timeout=60)
print("== annotate restart in log ==")
_remote.run(c, (
    "echo \"[signoff-restart $(date -u +%FT%T)] driver restarted so the "
    "MK_CSE_ROUND_TIMEOUT patch (16:37, after the 16:34 launch) takes effect; "
    "watchdog now 600s, budget 5400s\" >> /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log"
), timeout=60)
print("== relaunch ==")
_remote.run(c, LAUNCH, timeout=60)
time.sleep(10)
print("== verify single driver, effective config ==")
_remote.run(c, (
    "ps aux | grep 'run_e1_cse_falsify.py.*signoff_[r]equeue' | wc -l; "
    "tail -4 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log; "
    "grep -o '\"round_timeout_s\": [0-9]*' /root/mk_v2_runs/e1/cse_run_manifest_lane3_signoff_requeue.json"
), timeout=60)
c.close()
print("RESTART_DONE")
