import time

import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_signoff_orch_remote.py", "/root/mk_v2/_signoff_orch.py")
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile "
               "_signoff_orch.py && echo COMPILE_OK", timeout=120)
_remote.run(c, (
    "cd /root/mk_v2 && nohup /root/miniconda3/bin/python -u _signoff_orch.py "
    ">> /root/mk_v2_runs/signoff_orch_stdout.log 2>&1 & echo ORCH_PID=$!"
), timeout=60)
time.sleep(10)
_remote.run(c, (
    "tail -20 /root/mk_v2_runs/signoff_orch.log 2>/dev/null; echo ---PS---; "
    "ps aux | grep '_signoff_[o]rch' | awk '{print $2}'"
), timeout=60)
c.close()
print("ORCH_LAUNCHED")
