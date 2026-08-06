
import os, time
from pathlib import Path
def ppid(p):
    try:
        for l in open("/proc/%d/status" % p):
            if l.startswith("PPid:"):
                return int(l.split()[1])
    except OSError:
        pass
    return 0
excl, p = set(), os.getpid()
while p and p != 1:
    excl.add(p); p = ppid(p)
now = time.time()
for e in sorted(os.listdir("/proc"), key=lambda x: int(x) if x.isdigit() else 0):
    if not e.isdigit() or int(e) in excl:
        continue
    try:
        cl = Path("/proc/%s/cmdline" % e).read_bytes().replace(b"\0", b" ").decode("utf-8","replace").strip()
        st = os.stat("/proc/%s" % e)
    except OSError:
        continue
    if any(t in cl for t in ("_wc_audit", "mutant_wor" + "ker", "ninja", "cicc", "cc1plus", "nvcc", "gcc")):
        print("%6s age=%5.0fs %s" % (e, now - st.st_ctime, cl[:150]))
