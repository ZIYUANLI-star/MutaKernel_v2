"""Observe the P37 verification window and the trigger's give-way behaviour."""
import io

import _remote

SCRIPT = r'''
import json, os, time
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
OUT = Path("/root/mk_v2_runs/e3_b9_calib")
print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))

print("[final-window dirs]")
for d in sorted(E1.glob("final_window*")):
    if d.is_dir():
        cfgs = sorted(d.glob("cfg_*.json"))
        ress = sorted(d.glob("res_*.json"))
        print("  %-30s cfg=%d res=%d mtime=%s"
              % (d.name, len(cfgs), len(ress),
                 time.strftime("%H:%M:%S", time.localtime(d.stat().st_mtime))))
        for p in cfgs[:12]:
            r = d / p.name.replace("cfg_", "res_")
            print("     %-52s res=%s" % (p.name, r.is_file()))
    elif d.is_file():
        print("  file %-28s %d bytes mtime=%s"
              % (d.name, d.stat().st_size,
                 time.strftime("%H:%M:%S", time.localtime(d.stat().st_mtime))))

print("\n[final-window logs]")
for p in sorted(Path("/root/mk_v2_runs").glob("*final_window*")) + \
         sorted(E1.glob("*final_window*.log")):
    if p.is_file() and p.suffix in (".log", ".txt", ".json"):
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        print("  ---- %s (%d lines) ----" % (p, len(lines)))
        for line in lines[-14:]:
            print("     ", line[:190])

print("\n[chain trigger log tail]")
log = OUT / "chain_trigger.log"
for line in log.read_text(encoding="utf-8").splitlines()[-14:]:
    print("  ", line[:200])

print("\n[stage1 chain log tail]")
log = OUT / "stage1_chain.log"
for line in log.read_text(encoding="utf-8").splitlines()[-6:]:
    print("  ", line[:200])

print("\n[markers]")
for name in ("CHAIN_TRIGGER_FIRED", "CHAIN_TRIGGER_EXIT", "STAGE1_FIRED",
             "STAGE1_BLOCKED", "PAUSED_FOR_SIGNOFF_RERUN", "queue_state.json"):
    print("  %-28s %s" % (name, (OUT / name).is_file()))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_fw_watch.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_fw_watch.py", timeout=300)
c.close()
