"""Replace the stage-2 guard with a fresh instance (restart counters reset).

Safe because the guard only acts when a lane driver is *not* running; the
live drivers are untouched.
"""
import time
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "pgrep -f 'bash guard_b9_v2.sh' | head -3"), timeout=30, echo=False)
pids = [p for p in o.split() if p.strip().isdigit()]
print("old guard pids:", pids)
if pids:
    _remote.run(c, "kill %s" % " ".join(pids), timeout=30, echo=False)
    time.sleep(2)
_, o, _ = _remote.run(c, (
    "cd /root/mk_v2_runs/e3_b9_calib && "
    "nohup env LANES=2 BUDGET_GB=240 bash guard_b9_v2.sh "
    ">> guard_b9_v2_stage2.out 2>&1 < /dev/null & echo NEWPID=$!"),
    timeout=30, echo=False)
print(o)
time.sleep(5)
_, o, _ = _remote.run(c, (
    "pgrep -af '[g]uard_b9_v2.sh|[_]b9_calib_driver_v2' | head -6; echo ---; "
    "tail -2 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log"),
    timeout=30, echo=False)
print(o)
c.close()
print("GUARD_REFRESH_DONE")
