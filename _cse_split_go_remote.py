#!/usr/bin/env python3
"""One-shot remote switch: stop CSE lane0, start split lanes 3/4/5 + guard.

Runs ON the A800:  /root/miniconda3/bin/python /root/mk_v2/_cse_split_go.py

Preconditions (hard): CSE_DONE_LANE1 and CSE_DONE_LANE2 markers exist and
cse_lane_plan.json has 6 lanes.  Kill discipline: guard first via pidfile,
then the lane0 driver by exact PID, then its workers by PPID.
"""
import json
import os
import subprocess
import time
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
RUNS = Path("/root/mk_v2_runs")
ENV_BASE = ("PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
            "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext")

for marker in ("CSE_DONE_LANE1", "CSE_DONE_LANE2"):
    if not (E1 / marker).exists():
        raise SystemExit(f"ABORT: {marker} missing; light lanes not finished")
plan = json.loads((E1 / "cse_lane_plan.json").read_text())
if len(plan["lanes"]) != 6:
    raise SystemExit("ABORT: cse_lane_plan.json lacks split lanes 3/4/5")

print("== stop guard ==")
pidfile = RUNS / "e1_guard.pid"
if pidfile.exists():
    try:
        os.kill(int(pidfile.read_text().strip()), 9)
        print("guard killed:", pidfile.read_text().strip())
    except (ProcessLookupError, ValueError):
        print("guard already gone")
    pidfile.unlink(missing_ok=True)

print("== stop lane0 driver + workers ==")
ps = subprocess.run(["ps", "-eo", "pid,ppid,args"], capture_output=True,
                    text=True).stdout.splitlines()
driver = None
for line in ps:
    if ("run_e1_cse_falsify.py" in line and "--lane 0" in line
            and "miniconda3/bin/python" in line):
        driver = int(line.split()[0])
        print("lane0 driver:", line.strip()[:110])
if driver is None:
    print("WARNING: lane0 driver not found (already stopped?)")
else:
    victims = [driver]
    for line in ps:
        parts = line.split()
        if "_mutant_worker.py" in line and len(parts) > 1 and parts[1] == str(driver):
            victims.append(int(parts[0]))
            print("lane0 worker:", line.strip()[:110])
    for pid in victims:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
    time.sleep(2)

print("== account check ==")
likely_lane0 = set()
lane0_kernels = set(plan["lanes"][0]["kernels"])
for line in open(E1 / "equiv_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if (row.get("evidence_grade") == "LIKELY_EQUIVALENT"
            and row["kernel"] in lane0_kernels):
        likely_lane0.add(row["probe_id"])
done = set()
for f in sorted(E1.glob("cse_completed_lane*.json")):
    done |= set(json.load(open(f)))
legacy = E1 / "cse_falsify_completed.json"
if legacy.exists():
    done |= set(json.load(open(legacy)))
pending = likely_lane0 - done
split_kernels = {k for i in (3, 4, 5) for k in plan["lanes"][i]["kernels"]}
pending_covered = {p for p in pending}
assert len(likely_lane0) == 206, f"lane0 targets {len(likely_lane0)} != 206"
assert len(likely_lane0 & done) + len(pending) == 206
kernels_of_pending = {row_k for row_k in
                      {p.split("__", 1)[0] for p in pending}}
assert kernels_of_pending <= split_kernels, (
    f"pending kernels not covered: {kernels_of_pending - split_kernels}")
print(f"account OK: done={len(likely_lane0 & done)} pending={len(pending)} "
      f"(sum 206); pending kernels covered by lanes 3/4/5")

print("== install guard v2 + launch lanes 3/4/5 ==")
subprocess.run(["cp", str(RUNS / "e1_guard_cse_split.sh"), str(RUNS / "e1_guard.sh")],
               check=True)
subprocess.run(["chmod", "+x", str(RUNS / "e1_guard.sh")], check=True)
for lane, frac in ((3, 0.92), (4, 0.45), (5, 0.45)):
    cmd = (f"cd /root/mk_v2 && nohup env {ENV_BASE} "
           f"MK_GPU_MEMORY_FRACTION={frac} "
           "/root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py "
           "--out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench "
           "--timeout 1800 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json "
           f"--lane {lane} >> /root/mk_v2_runs/e1_cse_lane{lane}.log 2>&1 &")
    os.system(cmd)
    print(f"lane {lane} launched (fraction {frac})")
    time.sleep(2)
os.system(f"nohup bash {RUNS}/e1_guard.sh > /dev/null 2>&1 &")
print("guard launched")

time.sleep(20)
ps2 = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                     text=True).stdout
count = sum(1 for l in ps2.splitlines()
            if "run_e1_cse_falsify.py" in l and "miniconda3/bin/python" in l)
print(f"drivers running: {count} (expect 3)")
for lane in (3, 4, 5):
    log = RUNS / f"e1_cse_lane{lane}.log"
    if log.exists():
        print(f"lane{lane}:", open(log, encoding="utf-8",
                                   errors="replace").read().splitlines()[-1][:160])
print("CSE_SPLIT_GO_DONE")
