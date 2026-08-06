"""Confirm stage-2 drivers are stable (no more restarts)."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "pgrep -af '[_]b9_calib_driver_v2' | head -4; echo ---; "
    "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; echo ---; "
    "tail -3 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log; echo ---; "
    "tail -3 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log"),
    timeout=60, echo=False)
print(o)
c.close()
