"""Kill the B9 lane drivers + in-flight units by explicit PID.

`pkill -f` self-matched the SSH command line last time and severed the session
before the drivers were signalled, so the PIDs are resolved on the remote side
and filtered against our own shell PID instead.
"""
import _remote

SCRIPT = r'''
import os
import signal
import subprocess
import time

MY = {os.getpid(), os.getppid()}


def pids(pattern):
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout
    return [int(x) for x in out.split() if int(x) not in MY]


def kill(pat, sig, label):
    ps = pids(pat)
    for p in ps:
        try:
            os.kill(p, sig)
        except ProcessLookupError:
            pass
    print(f"{label}: signalled {ps or 'none'}")


# drivers first so no further units are spawned, then the in-flight units
kill("_b9_calib_driver.py", signal.SIGKILL, "lane drivers")
time.sleep(2)
kill("guard_b9.sh", signal.SIGKILL, "guard")
time.sleep(1)
kill("run_e3_external.py run --plan /root/mk_v2_runs/e3_b9_calib", signal.SIGKILL, "units")
time.sleep(4)
for pat, label in (("_b9_calib_driver.py", "drivers"),
                   ("guard_b9.sh", "guard"),
                   ("run_e3_external.py run --plan /root/mk_v2_runs/e3_b9_calib", "units")):
    print(f"remaining {label}: {pids(pat) or 'none'}")
print("--- cse worker (must survive) ---")
print(subprocess.run("ps aux | grep '_mutant_[w]orker' | awk '{print $2,$3,$4}'",
                     shell=True, capture_output=True, text=True).stdout.strip())
print("--- gpu ---")
print(subprocess.run(
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader",
    shell=True, capture_output=True, text=True).stdout.strip())
print("--- oom events ---")
print(subprocess.run(
    "cat /sys/fs/cgroup/memory.events 2>/dev/null || "
    "cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null",
    shell=True, capture_output=True, text=True).stdout.strip())
print("B9_KILL_DONE")
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_b9_pause_remote.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python -u /root/mk_v2/_b9_pause_remote.py", timeout=180)
c.close()
