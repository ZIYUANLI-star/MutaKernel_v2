"""Emergency: kill ALL duplicate CSE drivers/guards, repair lane files
(dedupe obs by probe_id, rebuild completed), relaunch exactly one set."""
import json
import time

import _remote

c = _remote.connect()

print("===== kill everything CSE (by exact pid list) =====")
_, out, _ = _remote.run(c, "ps -eo pid,args", timeout=30, echo=False)
targets = []
for line in out.splitlines():
    if (("run_e1_cse_falsify.py" in line and "python" in line)
            or "e1_guard.sh" in line
            or "_mutant_worker.py" in line
            or "CSE0_LAUNCHED" in line or "CSE1_LAUNCHED" in line
            or "CSE2_LAUNCHED" in line):
        try:
            pid = int(line.split()[0])
        except ValueError:
            continue
        targets.append(pid)
        print("kill:", line.strip()[:110])
if targets:
    _remote.run(c, f"kill -9 {' '.join(map(str, targets))} 2>/dev/null; sleep 2; "
                   "rm -f /root/mk_v2_runs/e1_guard.pid; "
                   "ps -eo args | grep -E 'run_e1_cse|e1_guard|_mutant_worker' | grep -v grep || echo ALL_CLEAR",
                timeout=30)

print("===== repair lane files (dedupe + rebuild completed) =====")
REPAIR = r'''
import json
from pathlib import Path
E1 = Path("/root/mk_v2_runs/e1")
for lane in (0, 1, 2):
    obs = E1 / f"cse_observations_lane{lane}.jsonl"
    done = E1 / f"cse_completed_lane{lane}.json"
    if not obs.exists():
        print(f"lane{lane}: no obs yet")
        done.unlink(missing_ok=True)
        continue
    seen, kept, dropped = set(), [], 0
    for line in open(obs, encoding="utf-8"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            dropped += 1
            continue
        if row["probe_id"] in seen:
            dropped += 1
            continue
        seen.add(row["probe_id"])
        kept.append(line if line.endswith("\n") else line + "\n")
    with open(obs, "w", encoding="utf-8") as fh:
        fh.writelines(kept)
    done.write_text(json.dumps(sorted(seen)))
    print(f"lane{lane}: kept={len(kept)} dropped_dupes_or_partial={dropped}")
print("REPAIR_OK")
'''
sftp = c.open_sftp()
import io
sftp.putfo(io.BytesIO(REPAIR.encode()), "/root/mk_v2/_e1_cse_repair.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_e1_cse_repair.py", timeout=60)

print("===== relaunch ONE set =====")
for lane, fraction in ((0, 0.92), (1, 0.45), (2, 0.45)):
    cmd = (
        "cd /root/mk_v2 && nohup env "
        "PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
        "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
        f"MK_GPU_MEMORY_FRACTION={fraction} "
        "/root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py "
        "--out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench "
        "--timeout 1800 "
        "--lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json "
        f"--lane {lane} "
        f">> /root/mk_v2_runs/e1_cse_lane{lane}.log 2>&1 & echo L{lane}_UP"
    )
    try:
        _remote.run(c, cmd, timeout=15)
    except Exception as exc:
        print(f"lane {lane} (tolerated):", type(exc).__name__)
    time.sleep(3)
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_UP", timeout=15)
except Exception as exc:
    print("guard (tolerated):", type(exc).__name__)

time.sleep(25)
print("===== verify single set =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,args | awk '/run_e1_cse_falsify.py --/ && !/awk/ {print $1, $(NF-1), $NF}'; "
               "pgrep -fc e1_guard.sh; echo guards_above", timeout=30)
_remote.run(c, "tail -n 1 /root/mk_v2_runs/e1_cse_lane0.log; tail -n 1 /root/mk_v2_runs/e1_cse_lane1.log; tail -n 1 /root/mk_v2_runs/e1_cse_lane2.log", timeout=30)
c.close()
print("DEDUP_FIX_DONE")
