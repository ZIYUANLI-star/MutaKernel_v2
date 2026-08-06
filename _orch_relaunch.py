"""Replace the running orchestrator with the self-match-safe version."""
import time

import _remote

SCRIPT = r'''
import os
import signal
import subprocess
import time

mine = {os.getpid(), os.getppid()}
out = subprocess.run(["pgrep", "-f", "_signoff_[o]rch.py"],
                     capture_output=True, text=True).stdout
pids = [int(x) for x in out.split() if int(x) not in mine]
for p in pids:
    try:
        os.kill(p, signal.SIGKILL)
    except ProcessLookupError:
        pass
print("killed old orchestrator:", pids or "none")
time.sleep(2)
out = subprocess.run(["pgrep", "-f", "_signoff_[o]rch.py"],
                     capture_output=True, text=True).stdout
print("remaining:", [x for x in out.split() if int(x) not in mine] or "none")
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_orch_kill.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python -u /root/mk_v2/_orch_kill.py", timeout=90)

sftp = c.open_sftp()
sftp.put("_signoff_orch_remote.py", "/root/mk_v2/_signoff_orch.py")
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile "
               "_signoff_orch.py && echo COMPILE_OK", timeout=120)
# setsid + closed stdin so the exec channel does not stay open
_remote.run(c, (
    "cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u _signoff_orch.py "
    ">> /root/mk_v2_runs/signoff_orch_stdout.log 2>&1 < /dev/null & "
    "echo SPAWNED; exit 0"
), timeout=45)
time.sleep(12)
_remote.run(c, (
    "ps aux | grep '_signoff_[o]rch.py' | awk '{print $2, $9}'; echo ---LOG---; "
    "tail -8 /root/mk_v2_runs/signoff_orch.log"
), timeout=60)
c.close()
print("RELAUNCH_DONE")
