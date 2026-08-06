"""Find the original planner that built full unit records; pause guard first."""
import _remote

c = _remote.connect()
# pause the guard loop via its own brake marker so lanes stop churning
_, o, _ = _remote.run(c, (
    "touch /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN && echo PAUSED; "
    "grep -l 'stage2_deferred' /root/mk_v2/*.py 2>/dev/null; echo ---; "
    "grep -l 'est_peak_gb' /root/mk_v2/*.py 2>/dev/null | head; echo ---; "
    "grep -n 'reduction_heavy' /root/mk_v2/*.py 2>/dev/null | head -20"),
    timeout=60, echo=False)
print(o)
c.close()
