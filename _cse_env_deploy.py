"""Upload the resource-degraded grading fix, remote pytest, reprocess."""
import _remote

FILES = [
    ("scripts/run_e1_cse_falsify.py", "/root/mk_v2/scripts/run_e1_cse_falsify.py"),
    ("tests/test_e1_cse_lanes.py", "/root/mk_v2/tests/test_e1_cse_lanes.py"),
    ("_cse_env_reprocess_remote.py", "/root/mk_v2/_cse_env_reprocess_remote.py"),
]

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("PUT", local)
sftp.close()
print("===== remote pytest =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests -x -q 2>&1 | tail -3", timeout=1500)
print("===== offline env reprocess =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python _cse_env_reprocess_remote.py", timeout=180)
c.close()
print("ENV_DEPLOY_DONE")
