import time
import _remote

c = _remote.connect()
ts = time.strftime("%Y%m%d_%H%M%S")

# 1) backup remote driver
print("=== backup remote driver ===")
_remote.run(c, f"cp -v /root/mk_v2/scripts/run_e1_cse_falsify.py "
               f"/root/mk_v2/scripts/run_e1_cse_falsify.py.bak_p53skip_{ts}", timeout=30)

# 2) upload fixed driver, skip config, test
sftp = c.open_sftp()
puts = [
    ("_dl_run_e1_cse_falsify.py", "/root/mk_v2/scripts/run_e1_cse_falsify.py"),
    ("_dl_cse_policy_skip.json", "/root/mk_v2_runs/e1/cse_policy_skip.json"),
    ("_dl_test_cse_policy_skip.py", "/root/mk_v2/tests/test_cse_policy_skip.py"),
]
for local, remote in puts:
    sftp.put(local, remote)
    print("uploaded", local, "->", remote)
sftp.close()

# 3) syntax check + skip config sanity
print("=== py_compile driver ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile scripts/run_e1_cse_falsify.py && echo COMPILE_OK", timeout=60)
print("=== skip config parses ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"from scripts.run_e1_cse_falsify import load_policy_skip; from pathlib import Path; print(load_policy_skip(Path('/root/mk_v2_runs/e1')))\"", timeout=60)
c.close()
