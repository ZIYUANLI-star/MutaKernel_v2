"""Upload the partial-evidence fix, run remote tests, then regrade offline."""
import _remote

FILES = [
    ("scripts/run_e1_cse_falsify.py", "/root/mk_v2/scripts/run_e1_cse_falsify.py"),
    ("tests/test_e1_cse_lanes.py", "/root/mk_v2/tests/test_e1_cse_lanes.py"),
    ("_cse_regrade_remote.py", "/root/mk_v2/_cse_regrade_remote.py"),
]

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("PUT", local)
sftp.close()

print("===== remote pytest =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests -x -q 2>&1 | tail -3", timeout=1500)
print("===== offline regrade + witness backfill + plan v3 =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python _cse_regrade_remote.py", timeout=300)
c.close()
print("FIX_DEPLOY_DONE")
