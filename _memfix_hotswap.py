#!/usr/bin/env python3
"""Hot-swap cse_mem_fix_v1.1 (worker + tests only, no process restarts):
stage -> gate tests against staged worker -> atomic mv into place ->
full tests. Running workers keep their loaded code; next spawns pick v1.1."""
import _remote

c = _remote.connect()
r = lambda cmd, t=120: _remote.run(c, cmd, timeout=t)

sftp = c.open_sftp()
sftp.put("_memfix_mutant_worker.py", "/root/mk_v2_staging/_mutant_worker.py")
sftp.put("_memfix_test_cse_memfix.py",
         "/root/mk_v2_staging/test_cse_memfix.py")
sftp.close()
print("uploaded v1.1")

r("/root/miniconda3/bin/python -m py_compile "
  "/root/mk_v2_staging/_mutant_worker.py "
  "/root/mk_v2_staging/test_cse_memfix.py && echo PY_COMPILE_OK")
r("cd /root/mk_v2 && MK_WORKER_PATH=/root/mk_v2_staging/_mutant_worker.py "
  "/root/miniconda3/bin/python -m pytest -q "
  "/root/mk_v2_staging/test_gen_opt_bitexact.py "
  "/root/mk_v2_staging/test_cse_memfix.py 2>&1 | tail -3", 600)

print("### install (atomic mv, no restarts)")
r("cp /root/mk_v2/scripts/_mutant_worker.py "
  "/root/mk_v2/scripts/_mutant_worker.py.bak_20260729_v1_0 && "
  "cp /root/mk_v2_staging/_mutant_worker.py "
  "/root/mk_v2/scripts/.new_mutant_worker.py && "
  "mv -f /root/mk_v2/scripts/.new_mutant_worker.py "
  "/root/mk_v2/scripts/_mutant_worker.py && "
  "cp /root/mk_v2_staging/test_cse_memfix.py "
  "/root/mk_v2/tests/test_cse_memfix.py && echo INSTALL_OK")
r("cd /root/mk_v2 && /root/miniconda3/bin/python -m pytest tests -q "
  "2>&1 | tail -2", 600)
r("pgrep -af 'run_e1_cse_falsify.py.*--lane [35]' | awk '{print $1}' ; "
  "pgrep -af 'scripts/_mutant_worker.py' | grep -c mutant")
c.close()
print("HOTSWAP_DONE")
