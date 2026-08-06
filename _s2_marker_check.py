"""Verify DONE marker naming consistency between driver, guard, probe."""
import _remote as R

c = R.connect()
R.run(c, "grep -n 'DONE_LANE' /root/mk_v2/_b9_calib_driver_v2.py", timeout=60)
R.run(c, "ls /root/mk_v2_runs/e3_b9_calib/ | grep DONE", timeout=60)
c.close()
print("MARKER_CHECK_DONE")
