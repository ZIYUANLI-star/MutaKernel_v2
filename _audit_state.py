"""Is the methodology audit finished, or merely between workers?

Decides whether the brake the deployed trigger just lifted still needs to be in
place.  Read-only.
"""
import io

import _remote

SCRIPT = r'''
import json, os, time
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
RUNS = Path("/root/mk_v2_runs")
OUT = Path("/root/mk_v2_runs/e3_b9_calib")
WC = E1 / "witness_confirmation"


def ppid_of(pid):
    try:
        for line in open("/proc/%d/status" % pid, encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def scan(needle):
    excluded, pid = set(), os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        pid = ppid_of(pid)
    hits = []
    for e in os.listdir("/proc"):
        if not e.isdigit() or int(e) in excluded:
            continue
        try:
            cl = Path("/proc/%s/cmdline" % e).read_bytes().replace(
                b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        if needle in cl:
            hits.append((int(e), cl[:130]))
    return hits


print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
print("[audit processes]")
for needle in ("witness_confirmation", "wc_", "WC_", "mutant_" + "worker",
               "_wc", "audit"):
    hits = scan(needle)
    if hits:
        print("  %-22s %s" % (needle, hits))
print("  (none listed above means no audit process is running right now)")

print("\n[witness_confirmation tree]")
if WC.is_dir():
    for p in sorted(WC.rglob("*")):
        try:
            st = p.stat()
        except OSError:
            continue
        kind = "dir " if p.is_dir() else "file"
        print("  %s %-72s %9d %s" % (kind, str(p.relative_to(WC)), st.st_size,
                                     time.strftime("%H:%M:%S",
                                                   time.localtime(st.st_mtime))))
else:
    print("  (absent)")

print("\n[audit logs / markers under mk_v2_runs]")
for p in sorted(RUNS.glob("*")):
    name = p.name.lower()
    if any(k in name for k in ("witness", "wc", "audit")) and p.is_file():
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        print("  ---- %s (%d lines, mtime %s) ----"
              % (p.name, len(lines),
                 time.strftime("%H:%M:%S", time.localtime(p.stat().st_mtime))))
        for line in lines[-16:]:
            print("     ", line[:180])

print("\n[chain trigger: did it lift the marker?]")
for line in (OUT / "chain_trigger.log").read_text(
        encoding="utf-8").splitlines()[-16:]:
    print("  ", line[:200])

print("\n[archive: lifted markers]")
arch = OUT / "archive"
if arch.is_dir():
    for p in sorted(arch.glob("PAUSED_FOR_SIGNOFF_RERUN*")):
        print("   %-54s mtime=%s" % (p.name,
              time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))))

print("\n[B9 right now]")
print("  pause marker:", (OUT / "PAUSED_FOR_SIGNOFF_RERUN").is_file())
st = json.loads((OUT / "queue_state.json").read_text())
print("  pending=%d claimed=%s done=%d" % (len(st["pending"]),
                                           list(st["claimed"]), len(st["done"])))
for uid, cl in st["claimed"].items():
    print("   in flight: %-22s lane=%s pid=%s since=%s reserve=%.1f GiB"
          % (uid, cl["lane"], cl["pid"], cl["since"], cl["reserve_gb"]))
print("  lanes:", scan("calib_driver_v2.py"))
for name in ("lane_v2_0.log", "lane_v2_1.log"):
    p = OUT / name
    if p.is_file():
        print("  [%s]" % name)
        for line in p.read_text().splitlines()[-3:]:
            print("     ", line[:170])


def oom():
    for p in ("/sys/fs/cgroup/memory.events",
              "/sys/fs/cgroup/memory/memory.oom_control"):
        try:
            for line in open(p, encoding="utf-8"):
                if line.startswith("oom_kill "):
                    return int(line.split()[1])
        except OSError:
            continue
    return None


print("  oom_kill:", oom(), "(baseline 20)")
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_audit_state.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_audit_state.py", timeout=300)
c.close()
