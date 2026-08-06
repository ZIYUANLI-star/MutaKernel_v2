
import os, signal, time
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
targets = []
for e in os.listdir("/proc"):
    if not e.isdigit() or int(e) in excl:
        continue
    try:
        cl = Path("/proc/%s/cmdline" % e).read_bytes().replace(b"\0", b" ").decode("utf-8","replace")
    except OSError:
        continue
    if "_wc_audit.py" in cl or ("scratch/cfg_" in cl and "witness_confirmation" in cl):
        targets.append((int(e), cl.strip()[:140]))
for pid, cl in targets:
    print("TERM", pid, cl)
for pid, _ in targets:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        print("  term failed", pid, exc)
time.sleep(8)
for pid, _ in targets:
    if os.path.exists("/proc/%d" % pid):
        try:
            os.kill(pid, signal.SIGKILL); print("KILL", pid)
        except OSError:
            pass
time.sleep(3)
left = [pid for pid, _ in targets if os.path.exists("/proc/%d" % pid)]
print("still alive:", left)
