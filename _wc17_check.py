import _remote
c = _remote.connect()
R = _remote.run
R(c, "tail -15 /root/mk_v2_runs/e1/witness_confirmation/control_stdout.log; echo '--- cells:'; ls /root/mk_v2_runs/e1/witness_confirmation/cells 2>/dev/null | wc -l; nvidia-smi --query-gpu=memory.used --format=csv,noheader")
script = r'''
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
'''
open("_wc17_tmp.py","w").write(script)
s = c.open_sftp(); s.put("_wc17_tmp.py", "/root/mk_v2/_wc17_tmp.py"); s.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc17_tmp.py", timeout=120)
c.close()
