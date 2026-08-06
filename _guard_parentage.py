"""Is there really more than one guard, or are those subshell wrappers?

The invariant that matters is one guard *loop*: two guards would restart lanes
independently and double the lane count back into the OOM regime.
"""
import io

import _remote

SCRIPT = r'''
import os, time
from pathlib import Path


def read(pid, name):
    try:
        return Path("/proc/%d/%s" % (pid, name)).read_text(errors="replace")
    except OSError:
        return ""


def info(pid):
    ppid = 0
    for line in read(pid, "status").splitlines():
        if line.startswith("PPid:"):
            ppid = int(line.split()[1])
    return ppid, read(pid, "cmdline").replace("\0", " ").strip(), \
        read(pid, "wchan").strip()


pids = [int(e) for e in os.listdir("/proc") if e.isdigit()]
print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
rows = []
for pid in sorted(pids):
    ppid, cl, wchan = info(pid)
    if "guard_b9" in cl or "calib_driver_v2" in cl:
        rows.append((pid, ppid, wchan, cl))
print("%-7s %-7s %-14s %s" % ("pid", "ppid", "wchan", "cmdline"))
for pid, ppid, wchan, cl in rows:
    print("%-7d %-7d %-14s %s" % (pid, ppid, wchan, cl[:100]))

known = {pid for pid, _, _, _ in rows}
print("\ninterpretation:")
for pid, ppid, wchan, cl in rows:
    if "guard_b9" not in cl:
        continue
    kids = [p for p in pids if info(p)[0] == pid]
    lane_kids = [k for k in kids if "calib_driver_v2" in info(k)[1]]
    if lane_kids:
        print("  pid %d is a SUBSHELL WRAPPER waiting on lane %s "
              "(wchan=%s) -- not a second guard loop" % (pid, lane_kids, wchan))
    elif ppid == 1 or ppid not in known:
        print("  pid %d is the GUARD LOOP (ppid=%d, children=%s)"
              % (pid, ppid, kids))
    else:
        print("  pid %d: ppid=%d children=%s wchan=%s -- inspect"
              % (pid, ppid, kids, wchan))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_guard_parentage.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_guard_parentage.py", timeout=300)
c.close()
