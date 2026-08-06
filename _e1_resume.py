"""Relaunch the E1 baseline driver after the remote server reboot (resumes from completed.json)."""
import sys
import _remote

c = _remote.connect()

# 1. sanity: GPU up, checkpoint intact, no stray driver
_, out, _ = _remote.run(c, (
    "nvidia-smi --query-gpu=name,memory.used --format=csv,noheader; echo SEP; "
    "python3 -c \"import json; d=json.load(open('/root/mk_v2_runs/e1/completed.json')); print('completed:', len(d))\" 2>&1; echo SEP; "
    "wc -l < /root/mk_v2_runs/e1/baseline_observations.jsonl; echo SEP; "
    "ps aux | grep 'run_e1_probe_[s]tudy' | wc -l; echo SEP; "
    "head -3 /root/mk_v2_runs/e1_baseline.log"
), timeout=120, echo=False)
print(out)

if "--check" in sys.argv:
    c.close()
    print("CHECK_DONE")
    sys.exit(0)

# 2. relaunch (same env/args as the original launch; driver skips completed probes)
env = ("PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
       "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext")
launch = (
    f"cd /root/mk_v2 && nohup env {env} /root/miniconda3/bin/python -u "
    "scripts/run_e1_probe_study.py --phase baseline --kernelbench-root KernelBench "
    "--out-dir /root/mk_v2_runs/e1 --timeout 420 "
    ">> /root/mk_v2_runs/e1_baseline.log 2>&1 & echo LAUNCHED pid=$!"
)
_, out, _ = _remote.run(c, launch, timeout=60, echo=False)
print(out)

# 3. confirm it picked up the checkpoint
import time
time.sleep(20)
_, out, _ = _remote.run(c, (
    "ps aux | grep 'run_e1_probe_[s]tudy' | grep -v grep | wc -l; "
    "tail -c 800 /root/mk_v2_runs/e1_baseline.log"
), timeout=60, echo=False)
print(out)
c.close()
print("RESUME_DONE")
