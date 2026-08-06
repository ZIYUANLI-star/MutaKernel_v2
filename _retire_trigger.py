"""Retire the B9 chain trigger and its keepalive; hand every duty to the supervisor.

Order matters and is enforced by the remote script:

  1. deploy the rewired supervisor + its own keepalive, and verify the supervisor
     is running the new code (brake duty must be live *before* the trigger goes);
  2. write CHAIN_TRIGGER_EXIT -- keepalive_chain.sh checks it first and retires
     itself, so the trigger cannot be resurrected between steps 3 and 4;
  3. stop the trigger by explicit PID (never the process group: the trigger's
     old session id is shared by the guard and its lane wrappers);
  4. stop keepalive_chain.sh by explicit PID for determinism;
  5. start keepalive_stage1.sh;
  6. verify: guard alive, checkpoints unchanged, oom_kill unchanged, brake state
     unchanged, supervisor alive, trigger and its keepalive gone.
"""
import io
from pathlib import Path

import _remote

KEEPALIVE = r'''#!/bin/bash
# Keepalive for the B9 supervisor (_b9_stage1_chain.py).
#
# The supervisor holds an flock, so a duplicate launch exits immediately; the
# loop retires once stage 1 has recorded STAGE1_DONE.  Liveness is a /proc scan
# inside python -- never `pgrep -f`, which would match this script's own line.
#
# Restarting the supervisor is safe with respect to brakes: brakes live in files
# under brakes/, not in the process, and the derived marker is only removed after
# positively observing an empty holder set.  A gap in supervision therefore means
# "stays braked", never "brake released".
OUT=/root/mk_v2_runs/e3_b9_calib
PY=/root/miniconda3/bin/python
LOG=$OUT/keepalive_stage1.log

echo "$(date '+%F %T') keepalive_stage1 start pid=$$" >> "$LOG"
while true; do
  if [ -f "$OUT/STAGE1_DONE" ]; then
    echo "$(date '+%F %T') stage 1 recorded DONE -> keepalive retires" >> "$LOG"
    break
  fi
  if ! "$PY" /root/mk_v2/_b9_stage1_alive.py; then
    echo "$(date '+%F %T') supervisor absent -> relaunch" >> "$LOG"
    cd /root/mk_v2 && setsid "$PY" -u _b9_stage1_chain.py \
      >> "$OUT/stage1_chain_stdout.log" 2>&1 < /dev/null &
  fi
  sleep 120
done
'''

ALIVE = r'''#!/usr/bin/env python3
"""Exit 0 if a B9 supervisor process is alive, 1 otherwise (for the keepalive)."""
import sys

sys.path.insert(0, "/root/mk_v2")
import _b9_brake as brake

sys.exit(0 if brake.find_processes("_b9_stage1_chain.py") else 1)
'''

RETIRE = r'''
import json, os, signal, sys, time
from pathlib import Path
sys.path.insert(0, "/root/mk_v2")
import _b9_brake as brake

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
EXITED = OUT / "CHAIN_TRIGGER_EXIT"


def snapshot():
    state = json.loads((OUT / "queue_state.json").read_text())
    return {
        "pending": sorted(state["pending"]),
        "claimed": sorted(state["claimed"]),
        "done": len(state["done"]),
        "completed": {p.name: json.loads(p.read_text())
                      for p in sorted(OUT.glob("completed_v2_lane*.json"))},
        "rows": {p.name: len([x for x in p.read_text().splitlines() if x.strip()])
                 for p in sorted(OUT.glob("calibration_v2_lane*.jsonl"))},
        "oom": _oom(),
        "brake_holders": sorted(o for o, _ in brake.holders()),
        "derived_present": brake.derived_path().is_file(),
    }


def _oom():
    for p in ("/sys/fs/cgroup/memory.events",
              "/sys/fs/cgroup/memory/memory.oom_control"):
        try:
            for line in open(p, encoding="utf-8"):
                if line.startswith("oom_kill "):
                    return int(line.split()[1])
        except OSError:
            continue
    return None


print("=== retire the chain trigger  %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
supervisors = brake.find_processes("_b9_stage1_chain.py")
if not supervisors:
    sys.exit("REFUSING: no supervisor alive -- brake duty would be unowned")
print("supervisor alive :", [p for p, _ in supervisors])
before = snapshot()
print("before: pending=%d claimed=%s done=%d rows=%s oom=%s brake=%s"
      % (len(before["pending"]), before["claimed"], before["done"],
         before["rows"], before["oom"], before["brake_holders"]))

print("\n-- step 2: record the retirement so the old keepalive stands down")
EXITED.write_text(json.dumps({
    "retired_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "reason": ("retired by decision: its brake handling was ownership-blind and "
               "could release another party's PAUSED_FOR_SIGNOFF_RERUN during a "
               "gap between that party's workers.  Every live duty moved to "
               "_b9_stage1_chain.py, which brakes through the signed protocol in "
               "_b9_brake.py."),
    "duties_transferred": {
        "brake on critical path": "_b9_stage1_chain.BrakeDuty.poll",
        "release after brake": "_b9_brake.release, own holds only",
        "keep the guard alive": "_b9_stage1_chain.keep_guard_alive",
        "wave completion detection": "_b9_stage1_chain.wait_for_wave",
        "idempotency": "flock on stage1_chain.lock",
        "process/GPU detection": "_b9_brake.find_processes / gpu_compute_apps",
        "keepalive": "keepalive_stage1.sh",
    },
    "not_transferred_because_historical": [
        "wait for SIGNOFF_ORCH_DONE (satisfied 2026-07-30 20:14:14)",
        "pre-fire gate + fire() via resume_b9.sh --limit 13 (fired 20:28:37)",
    ],
}, indent=2), encoding="utf-8")
print("wrote", EXITED)

print("\n-- steps 3 and 4: stop the trigger and its keepalive by explicit PID")
for needle in ("_b9_chain_trigger.py", "keepalive_chain.sh"):
    for pid, cmdline in brake.find_processes(needle):
        if needle not in cmdline:
            continue
        try:
            os.kill(pid, signal.SIGTERM)   # single PID, never the process group
            print("  SIGTERM -> %-7d %s" % (pid, cmdline[:80]))
        except OSError as exc:
            print("  kill %d failed: %s" % (pid, exc))
time.sleep(5)
for needle in ("_b9_chain_trigger.py", "keepalive_chain.sh"):
    for pid, cmdline in brake.find_processes(needle):
        if needle in cmdline:
            try:
                os.kill(pid, signal.SIGKILL)
                print("  SIGKILL -> %d" % pid)
            except OSError:
                pass
time.sleep(3)

print("\n=== verification ===")
after = snapshot()
trigger_left = brake.find_processes("_b9_chain_trigger.py")
keepalive_left = brake.find_processes("keepalive_chain.sh")
print("trigger left        :", trigger_left or "none")
print("old keepalive left  :", keepalive_left or "none")
print("supervisor          :", brake.find_processes("_b9_stage1_chain.py") or "NONE")
print("guard               :", brake.find_processes("guard_b9") or "none")
print("lanes               :", brake.find_processes("calib_driver_v2.py") or "none")
print("after: pending=%d claimed=%s done=%d rows=%s oom=%s brake=%s"
      % (len(after["pending"]), after["claimed"], after["done"], after["rows"],
         after["oom"], after["brake_holders"]))

problems = []
if trigger_left:
    problems.append("trigger still alive")
if keepalive_left:
    problems.append("old keepalive still alive")
if not brake.find_processes("_b9_stage1_chain.py"):
    problems.append("supervisor is gone -- brake duty unowned")
for key in ("pending", "claimed", "done", "completed", "rows", "oom",
            "brake_holders", "derived_present"):
    if before[key] != after[key]:
        problems.append("%s changed: %r -> %r" % (key, before[key], after[key]))
print("\n" + ("RETIRE_VERIFIED" if not problems
              else "RETIRE_PROBLEMS " + "; ".join(problems)))
'''

c = _remote.connect()
sftp = c.open_sftp()
here = Path(__file__).resolve().parent
sftp.put(str(here / "_b9_stage1_chain.py"), "/root/mk_v2/_b9_stage1_chain.py")
sftp.putfo(io.BytesIO(KEEPALIVE.encode()),
           "/root/mk_v2_runs/e3_b9_calib/keepalive_stage1.sh")
sftp.putfo(io.BytesIO(ALIVE.encode()), "/root/mk_v2/_b9_stage1_alive.py")
sftp.putfo(io.BytesIO(RETIRE.encode()), "/root/_retire_trigger.py")
sftp.close()
print("uploaded supervisor, keepalive_stage1.sh, _b9_stage1_alive.py")

_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile "
               "_b9_stage1_chain.py _b9_stage1_alive.py && echo COMPILE_OK",
            timeout=300)
c.close()
print("RETIRE_PREP_DONE (run _retire_go.py to execute)")
