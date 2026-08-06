"""Check whether the stage-1 chainer is resident, and show its log."""
import io

import _remote

SCRIPT = r'''
import os, time
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")


def _ppid(pid):
    try:
        for line in open("/proc/%d/status" % pid, encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def find(needle):
    excluded, pid = set(), os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        pid = _ppid(pid)
    hits = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) in excluded:
            continue
        try:
            raw = Path("/proc/%s/cmdline" % entry).read_bytes()
        except OSError:
            continue
        cl = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if needle in cl:
            hits.append((int(entry), cl[:140]))
    return hits


print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
for needle in ("_b9_stage1_chain.py", "_b9_chain_trigger.py",
               "_b9_calib_driver_v2.py", "guard_b9", "_mutant_worker.py",
               "_signoff_orch.py"):
    print("%-24s %s" % (needle, find(needle) or "none"))
for name in ("stage1_chain.log", "stage1_chain_stdout.log", "chain_trigger.log"):
    p = OUT / name
    print("\n---- %s (exists=%s) ----" % (name, p.is_file()))
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]:
            print("  ", line[:200])
for name in ("CHAIN_TRIGGER_FIRED", "CHAIN_TRIGGER_EXIT", "STAGE1_FIRED",
             "STAGE1_BLOCKED", "STAGE1_DONE", "PAUSED_FOR_SIGNOFF_RERUN",
             "queue_state.json"):
    print("marker %-28s %s" % (name, (OUT / name).is_file()))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_s1_check.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_s1_check.py", timeout=300)
c.close()
