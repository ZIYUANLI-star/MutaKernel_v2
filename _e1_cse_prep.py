"""Upload CSE lane code + plan script, run remote tests, draft the plan,
and report equiv progress (all read-only w.r.t. run data)."""
import _remote

FILES = [
    ("scripts/run_e1_cse_falsify.py", "/root/mk_v2/scripts/run_e1_cse_falsify.py"),
    ("tests/test_e1_cse_lanes.py", "/root/mk_v2/tests/test_e1_cse_lanes.py"),
    ("_e1_cse_plan_remote.py", "/root/mk_v2/_e1_cse_plan_remote.py"),
]

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("PUT", local)
sftp.close()

print("===== equiv progress =====")
_remote.run(c, "date '+%F %T %z'; ls /root/mk_v2_runs/e1/EQUIV_DONE* 2>/dev/null; "
               "wc -l /root/mk_v2_runs/e1/equiv_observations_lane4_requeue.jsonl; "
               "tail -n 1 /root/mk_v2_runs/e1_equiv_lane4_requeue.log", timeout=30)
print("===== remote pytest =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests -x -q 2>&1 | tail -3", timeout=1500)
print("===== CSE plan draft =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python _e1_cse_plan_remote.py", timeout=300)
c.close()
print("CSE_PREP_DONE")
