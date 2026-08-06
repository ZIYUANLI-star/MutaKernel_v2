"""Checkpoint-safe lane3 queue reorder: stop guard + lane3 only, upload the
ordering fix, reorder the plan, restart lane3 + guard.  Lanes 4/5 untouched.
"""
import time

import _remote

FILES = [
    ("scripts/run_e1_cse_falsify.py", "/root/mk_v2/scripts/run_e1_cse_falsify.py"),
    ("tests/test_e1_cse_lanes.py", "/root/mk_v2/tests/test_e1_cse_lanes.py"),
    ("_cse_reorder_remote.py", "/root/mk_v2/_cse_reorder_remote.py"),
]

LANE3_CMD = (
    "cd /root/mk_v2 && nohup env "
    "PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
    "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
    "MK_GPU_MEMORY_FRACTION=0.92 "
    "/root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py "
    "--out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench "
    "--timeout 3600 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json "
    "--lane 3 >> /root/mk_v2_runs/e1_cse_lane3.log 2>&1 & echo L3_UP"
)

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("PUT", local)
sftp.close()

print("===== T0: stop guard (so it cannot resurrect old lane3) =====")
_remote.run(c, "date '+%F %T %z'; GP=$(cat /root/mk_v2_runs/e1_guard.pid 2>/dev/null); "
               "echo guard_pid: $GP; kill -9 $GP 2>/dev/null; rm -f /root/mk_v2_runs/e1_guard.pid; echo GUARD_STOPPED",
            timeout=30)

print("===== stop lane3 driver + worker by PID =====")
_, out, _ = _remote.run(c, "ps -eo pid,ppid,args", timeout=30, echo=False)
targets = []
for line in out.splitlines():
    if ("run_e1_cse_falsify.py" in line and "miniconda3/bin/python" in line
            and "--lane 3" in line):
        targets.append(int(line.split()[0]))
        print("lane3 driver:", line.strip()[:110])
for line in out.splitlines():
    parts = line.split()
    if "_mutant_worker.py" in line and len(parts) > 1 and \
            any(parts[1] == str(t) for t in targets):
        targets.append(int(parts[0]))
        print("lane3 worker:", line.strip()[:110])
if not targets:
    raise SystemExit("ABORT: lane3 driver not found")
_remote.run(c, f"kill -9 {' '.join(map(str, targets))} 2>/dev/null; sleep 2; "
               "ps -eo args | grep -E 'lane 3$' | grep -v grep || echo LANE3_STOPPED",
            timeout=30)

print("===== remote pytest (quick) =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests/test_e1_cse_lanes.py -x -q 2>&1 | tail -2", timeout=600)
print("===== reorder plan =====")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _cse_reorder_remote.py", timeout=120)

print("===== account check =====")
_remote.run(
    c,
    "/root/miniconda3/bin/python -c \""
    "import json; from pathlib import Path; E1=Path('/root/mk_v2_runs/e1');"
    "plan=json.load(open(E1/'cse_lane_plan.json'));"
    "lk=set(plan['lanes'][3]['kernels']);"
    "likely={json.loads(l)['probe_id'] for l in open(E1/'equiv_observations.jsonl') "
    "if json.loads(l).get('evidence_grade')=='LIKELY_EQUIVALENT' and json.loads(l)['kernel'] in lk};"
    "done=set();"
    "import glob;"
    "[done.update(json.load(open(f))) for f in glob.glob(str(E1/'cse_completed_lane*.json'))];"
    "print('lane3 targets:', len(likely), 'done:', len(likely & done), 'pending:', len(likely - done))\"",
    timeout=30,
)

print("===== restart lane3 + guard =====")
try:
    _remote.run(c, LANE3_CMD, timeout=15)
except Exception as exc:
    print("lane3 launch (tolerated):", type(exc).__name__)
time.sleep(3)
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_UP", timeout=15)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__)

time.sleep(30)
print("===== verify =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,args | awk '/run_e1_cse_falsify.py --out/ && /python/ && !/awk/ {print $1, $(NF-1), $NF}'; cat /root/mk_v2_runs/e1_guard.pid", timeout=30)
_remote.run(c, "grep 'cse-falsify (lane 3)' /root/mk_v2_runs/e1_cse_lane3.log | tail -1; "
               "ps -eo args | grep _mutant_worker | grep -v grep | head -3", timeout=30)
print("===== three-lane progress + memory =====")
_remote.run(c, "for L in 3 4 5; do echo -n \"lane$L obs: \"; wc -l < /root/mk_v2_runs/e1/cse_observations_lane$L.jsonl 2>/dev/null || echo 0; done; "
               "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
               "nvidia-smi --query-gpu=memory.used --format=csv,noheader", timeout=30)
c.close()
print("LANE3_REQUEUE_DONE")
