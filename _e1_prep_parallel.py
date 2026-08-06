"""Upload dual-lane code, run remote CPU-only tests, generate the lane plan.

Safe to run while the serial driver is still working (all steps read-only
w.r.t. run data except writing lane_plan.json).
"""
import _remote

FILES = [
    ("scripts/run_e1_probe_study.py", "/root/mk_v2/scripts/run_e1_probe_study.py"),
    ("tests/test_e1_lane_partition.py", "/root/mk_v2/tests/test_e1_lane_partition.py"),
    ("_e1_laneplan_remote.py", "/root/mk_v2/_e1_laneplan_remote.py"),
    ("_e1_merge_lanes_remote.py", "/root/mk_v2/_e1_merge_lanes_remote.py"),
]

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("PUT", local)
sftp.close()

print("===== pytest =====")
_remote.run(
    c,
    "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests -x -q 2>&1 | tail -6",
    timeout=1500,
)
print("===== lane plan =====")
_remote.run(
    c,
    "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python _e1_laneplan_remote.py",
    timeout=1200,
)
c.close()
print("PREP_DONE")
