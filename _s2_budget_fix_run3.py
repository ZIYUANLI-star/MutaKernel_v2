"""Upload surgery script, run it, relaunch guard at 105GiB, verify."""
import time
import _remote

c = _remote.connect()
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

_, o, _ = _remote.run(c, (
    "pkill -f '[g]uard_b9_v2.sh' 2>/dev/null; sleep 2; "
    "rm -f /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN; "
    "cd /root/mk_v2_runs/e3_b9_calib && "
    "setsid nohup env LANES=2 BUDGET_GB=105 bash guard_b9_v2.sh "
    ">> guard_b9_v2_stage2.out 2>&1 < /dev/null & echo GUARD_RELAUNCHED"),
    timeout=30, echo=False)
print(o)

time.sleep(75)
_, o, _ = _remote.run(c, (
    "pgrep -af '[g]uard_b9_v2.sh|[_]b9_calib_driver_v2' | head -5; echo ---; "
    "tail -3 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log; echo ---; "
    "tail -3 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo ---; "
    "tail -3 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log"),
    timeout=60, echo=False)
print(o)
c.close()
print("FIX_SEQUENCE_DONE")
