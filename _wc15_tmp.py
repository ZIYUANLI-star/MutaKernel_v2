
import os
from pathlib import Path
def ppid(p):
    try:
        for line in open("/proc/%d/status" % p):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0
excl, p = set(), os.getpid()
while p and p != 1:
    excl.add(p); p = ppid(p)
needles = ["_b9_calib_driver", "guard_b9", "_mutant_worker", "_b9_chain_trigger",
           "_b9_stage1_chain", "keepalive_chain"]
for e in sorted(os.listdir("/proc")):
    if not e.isdigit() or int(e) in excl:
        continue
    try:
        raw = Path("/proc/%s/cmdline" % e).read_bytes()
    except OSError:
        continue
    cl = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
    for n in needles:
        if n in cl:
            print(e, "->", cl[:150])
            break
print("--- markers ---")
import glob
for f in sorted(glob.glob("/root/mk_v2_runs/e3_b9_calib/*")):
    if os.path.basename(f).isupper() or "PAUSED" in f:
        print(" ", f)
