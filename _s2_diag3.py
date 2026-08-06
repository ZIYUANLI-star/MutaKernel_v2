"""Read lane driver logs to find why stage-2 drivers die instantly."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "echo ===LANE0===; tail -60 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; "
    "echo ===LANE1===; tail -30 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log"),
    timeout=60, echo=False)
print(o)
c.close()
