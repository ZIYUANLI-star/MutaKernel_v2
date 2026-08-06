"""Orchestrate the budget fix: pause, stop lanes, queue surgery, relaunch."""
import time
import _remote

c = _remote.connect()

# 1. pause marker so no guard restarts lanes while we operate
_remote.run(c, "touch /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN",
            timeout=30, echo=False)

# 2. stop drivers and their workers (TERM, then KILL leftovers)
_, o, _ = _remote.run(c, (
    "pkill -TERM -f '[_]b9_calib_driver_v2.py' 2>/dev/null; "
    "pkill -TERM -f 'run_e3_external.py run' 2>/dev/null; sleep 5; "
    "pkill -KILL -f '[_]b9_calib_driver_v2.py' 2>/dev/null; "
    "pkill -KILL -f 'run_e3_external.py run' 2>/dev/null; sleep 2; "
    "pgrep -af '[_]b9_calib_driver_v2|run_e3_external.py run' | head -3; "
    "echo LANES_STOPPED"), timeout=60, echo=False)
print(o)
if "LANES_STOPPED" not in o:
    raise SystemExit("failed to stop lanes")

# 3. queue surgery
sftp = c.open_sftp()
sftp.put("_s2_budget_fix_src.py", "/root/mk_v2/_s2_budget_fix.py")
sftp.close()
_, o, e = _remote.run(
    c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _s2_budget_fix.py",
    timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:\n" + e[-2000:])
if "S2_BUDGET_FIX_DONE" not in o:
    raise SystemExit("queue surgery failed")

# 4. kill old guard, relaunch with the safe budget, lift pause
_, o, _ = _remote.run(c, (
    "pkill -f 'bash guard_b9_v2.sh' 2>/dev/null; sleep 2; "
    "rm -f /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN; "
    "cd /root/mk_v2_runs/e3_b9_calib && "
    "setsid nohup env LANES=2 BUDGET_GB=105 bash guard_b9_v2.sh "
    ">> guard_b9_v2_stage2.out 2>&1 < /dev/null & echo GUARD_RELAUNCHED"),
    timeout=30, echo=False)
print(o)
c.close()
print("FIX_SEQUENCE_DONE")
