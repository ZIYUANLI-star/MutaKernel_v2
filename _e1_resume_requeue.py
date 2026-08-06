"""Relaunch the serial requeue driver + guard v5 after the power outage."""
import time

import _remote

RETRY_CMD = (
    "cd /root/mk_v2 && nohup env "
    "PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
    "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
    "MK_GPU_MEMORY_FRACTION=0.9 "
    "/root/miniconda3/bin/python -u scripts/run_e1_probe_study.py "
    "--phase equiv --kernelbench-root KernelBench "
    "--out-dir /root/mk_v2_runs/e1 --timeout 1800 "
    "--lane-plan /root/mk_v2_runs/e1/lane_plan.json "
    "--lane 4 --lane-tag requeue "
    ">> /root/mk_v2_runs/e1_equiv_lane4_requeue.log 2>&1 &"
)

c = _remote.connect()
print("===== guard script sanity (v5 on disk?) =====")
_remote.run(c, "head -4 /root/mk_v2_runs/e1_guard.sh; rm -f /root/mk_v2_runs/e1_guard.pid", timeout=20)

print("===== relaunch driver =====")
try:
    _remote.run(c, RETRY_CMD + " echo RETRY_RELAUNCHED", timeout=15)
except Exception as exc:
    print("driver launch (tolerated):", type(exc).__name__)
time.sleep(3)
print("===== relaunch guard =====")
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_RELAUNCHED", timeout=15)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__)

time.sleep(25)
print("===== verify =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,args | awk '/run_e1_probe_study|e1_guard/ && !/awk/ {print $1, $(NF-2), $(NF-1), $NF}'", timeout=30)
_remote.run(c, "tail -n 2 /root/mk_v2_runs/e1_equiv_lane4_requeue.log", timeout=30)
c.close()
print("RESUME_DONE")
