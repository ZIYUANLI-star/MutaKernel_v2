"""Upload the timeout-fix files and run the full CPU-only test suite remotely."""
import _remote

FILES = [
    ("scripts/_mutant_worker.py", "/root/mk_v2/scripts/_mutant_worker.py"),
    ("scripts/run_e1_probe_study.py", "/root/mk_v2/scripts/run_e1_probe_study.py"),
    ("tests/test_e1_timeout_grading.py", "/root/mk_v2/tests/test_e1_timeout_grading.py"),
]

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("PUT", local, "->", remote)
sftp.close()

print("===== pytest =====")
_remote.run(
    c,
    "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests -x -q 2>&1 | tail -12",
    timeout=1500,
)
c.close()
print("DEPLOY_DONE")
