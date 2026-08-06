"""Retry: stop lanes with self-safe patterns, queue surgery, relaunch."""
import time
import _remote

c = _remote.connect()

_, o, _ = _remote.run(c, (
    "pgrep -af '[_]b9_calib_driver_v2|[r]un_e3_external.py run' | head -6; "
    "echo ---STATE_END"), timeout=30, echo=False)
print("STATE BEFORE:\n" + o)

_, o, _ = _remote.run(c, (
    "pkill -TERM -f '[_]b9_calib_driver_v2.py'; "
    "pkill -TERM -f '[r]un_e3_external.py run'; sleep 5; "
    "pkill -KILL -f '[_]b9_calib_driver_v2.py' 2>/dev/null; "
    "pkill -KILL -f '[r]un_e3_external.py run' 2>/dev/null; sleep 2; "
    "pgrep -af '[_]b9_calib_driver_v2|[r]un_e3_external.py run' | head -3; "
    "echo LANES_STOPPED"), timeout=60, echo=False)
print(o)
if "LANES_STOPPED" not in o:
    raise SystemExit("failed to stop lanes")

_, o, e = _remote.run(
    c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _s2_budget_fix.py",
    timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:\n" + e[-2000:])
if "S2_BUDGET_FIX_DONE" not in o:
    raise SystemExit("queue surgery failed")

_, o, _ = _remote.run(c, (
    "pkill -f '[g]uard_b9_v2.sh' 2>/dev/null; sleep 2; "
    "rm -f /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN; "
    "cd /root/mk_v2_runs/e3_b9_calib && "
    "setsid nohup env LANES=2 BUDGET_GB=105 bash guard_b9_v2.sh "
    ">> guard_b9_v2_stage2.out 2>&1 < /dev/null & echo GUARD_RELAUNCHED"),
    timeout=30, echo=False)
print(o)
c.close()
print("FIX_SEQUENCE_DONE")
