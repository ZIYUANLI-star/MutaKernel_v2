"""Inspect equiv observations appended after the restart (line 68 onwards)."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_e1_checknew_remote.py", "/root/mk_v2/_e1_checknew_remote.py")
sftp.close()
_remote.run(c, "ps aux | grep -E 'run_e1_probe|e1_guard' | grep -v grep | awk '{print $2, $11, $12, $13}'", timeout=30)
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_e1_checknew_remote.py", timeout=60)
_remote.run(c, "tail -n 3 /root/mk_v2_runs/e1_equiv.log", timeout=30)
c.close()
print("VERIFY_DONE")
