"""Who re-created PAUSED_FOR_SIGNOFF_RERUN, and is the trigger still in fire()?"""
import io

import _remote

SCRIPT = r'''
import os, time
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
E1 = Path("/root/mk_v2_runs/e1")


def ts(p):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))


print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
m = OUT / "PAUSED_FOR_SIGNOFF_RERUN"
print("[pause marker] exists=%s" % m.is_file())
if m.is_file():
    st = m.stat()
    print("  mtime=%s ctime=%s size=%d uid=%d"
          % (ts(m), time.strftime("%H:%M:%S", time.localtime(st.st_ctime)),
             st.st_size, st.st_uid))
    print("  ---- content ----")
    for line in m.read_text(encoding="utf-8", errors="replace").splitlines():
        print("   ", line[:180])

print("\n[archive: lifted markers]")
arch = OUT / "archive"
if arch.is_dir():
    for p in sorted(arch.glob("PAUSED_FOR_SIGNOFF_RERUN*")):
        print("   %-52s %s" % (p.name, ts(p)))

print("\n[trigger process state]")


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
            state = wchan = "?"
            try:
                for line in open("/proc/%s/status" % entry, encoding="utf-8"):
                    if line.startswith("State:"):
                        state = line.split(None, 1)[1].strip()
            except OSError:
                pass
            hits.append((int(entry), state, cl[:120]))
    return hits


for needle in ("_b9_chain_trigger.py", "resume_b9.sh", "_b9_resume_prep.py",
               "guard_b9", "_b9_calib_driver_v2.py", "_b9_stage1_chain.py",
               "pause_b9.sh", "_mutant_worker.py", "run_e1_cse_falsify.py"):
    hits = find(needle)
    print("  %-26s %s" % (needle, hits or "none"))

print("\n[chain trigger log: full tail]")
for line in (OUT / "chain_trigger.log").read_text(
        encoding="utf-8").splitlines()[-16:]:
    print("  ", line[:210])

print("\n[chain trigger stdout tail]")
p = OUT / "chain_trigger_stdout.log"
if p.is_file():
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-16:]:
        print("  ", line[:210])

print("\n[recently modified files in the B9 dir]")
rows = []
for p in OUT.rglob("*"):
    try:
        if p.is_file():
            rows.append((p.stat().st_mtime, p))
    except OSError:
        continue
for mt, p in sorted(rows)[-18:]:
    print("   %s  %s" % (time.strftime("%H:%M:%S", time.localtime(mt)),
                         str(p).replace(str(OUT) + "/", "")))

print("\n[e1 final-window activity around 20:30-20:40]")
for d in sorted(E1.glob("final_window*")):
    try:
        print("   %-32s %s" % (d.name, ts(d)))
    except OSError:
        pass
for p in sorted(Path("/root/mk_v2_runs").glob("*final_window*")):
    try:
        print("   %-46s %s" % (p.name, ts(p)))
    except OSError:
        pass
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_pause_forensics.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_pause_forensics.py", timeout=300)
c.close()
