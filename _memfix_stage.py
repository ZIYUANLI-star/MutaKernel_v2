#!/usr/bin/env python3
"""Stage cse_mem_fix_v1 on the A800 and gate it with targeted tests."""
import _remote

c = _remote.connect()
_remote.run(c, "mkdir -p /root/mk_v2_staging", timeout=30)
sftp = c.open_sftp()
for loc, rem in [
    ("_memfix_mutant_worker.py", "/root/mk_v2_staging/_mutant_worker.py"),
    ("_memfix_run_e1_cse_falsify.py",
     "/root/mk_v2_staging/run_e1_cse_falsify.py"),
    ("_memfix_test_gen_opt_bitexact.py",
     "/root/mk_v2_staging/test_gen_opt_bitexact.py"),
    ("_memfix_test_cse_memfix.py", "/root/mk_v2_staging/test_cse_memfix.py"),
]:
    sftp.put(loc, rem)
    print("uploaded", rem)
sftp.close()

_remote.run(c, "/root/miniconda3/bin/python -m py_compile "
               "/root/mk_v2_staging/_mutant_worker.py "
               "/root/mk_v2_staging/run_e1_cse_falsify.py "
               "/root/mk_v2_staging/test_gen_opt_bitexact.py "
               "/root/mk_v2_staging/test_cse_memfix.py && echo PY_COMPILE_OK",
            timeout=120)
_remote.run(c, "cd /root/mk_v2 && "
               "MK_WORKER_PATH=/root/mk_v2_staging/_mutant_worker.py "
               "/root/miniconda3/bin/python -m pytest -q "
               "/root/mk_v2_staging/test_gen_opt_bitexact.py "
               "/root/mk_v2_staging/test_cse_memfix.py 2>&1 | tail -5",
            timeout=600)
c.close()
print("STAGE_DONE")
