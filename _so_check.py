"""Read the sign-off orchestrator's own log and requeue bookkeeping."""
import io

import _remote

SCRIPT = r'''
import json, time
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
for name in ("signoff_orch.log", "signoff_orch_stdout.log"):
    for p in (E1 / name, Path("/root/mk_v2_runs") / name):
        if p.is_file():
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            print("\n---- %s (%d lines) ----" % (p, len(lines)))
            for line in lines[-28:]:
                print("  ", line[:210])
            break

for name in ("cse_completed_lane3_signoff_requeue.json",
             "SIGNOFF_ORCH_DONE"):
    p = E1 / name
    print("\n%s exists=%s" % (name, p.is_file()))
    if p.is_file() and p.suffix == ".json":
        print("  ", p.read_text()[:600])

print("\n---- signoff run dirs ----")
for d in sorted(E1.glob("e1cse_*")):
    if not d.is_dir():
        continue
    cfgs = list(d.glob("cfg_*.json"))
    ress = list(d.glob("res_*.json"))
    if cfgs or ress:
        print("  %-24s cfg=%d res=%d mtime=%s"
              % (d.name, len(cfgs), len(ress),
                 time.strftime("%H:%M:%S", time.localtime(d.stat().st_mtime))))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_so_check.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_so_check.py", timeout=300)
c.close()
