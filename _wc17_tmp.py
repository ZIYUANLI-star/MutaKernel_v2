
import os
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
for e in sorted(os.listdir("/proc"), key=lambda x: int(x) if x.isdigit() else 0):
    if not e.isdigit() or int(e) in excl:
        continue
    try:
        cl = Path("/proc/%s/cmdline" % e).read_bytes().replace(b"\0", b" ").decode("utf-8","replace").strip()
    except OSError:
        continue
    if "_wc_audit" in cl or "_mutant_wor" + "ker" in cl:
        print(e, "->", cl[:170])
