"""Stop the running audit driver (explicit pid via /proc scan, never pkill -f),
redeploy the updated planner, and relaunch.  Completed cells are checkpointed."""
import _remote, time
c = _remote.connect()
R = _remote.run

killer = r'''
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
'''
open("_wc20_tmp.py", "w").write(killer)
s = c.open_sftp()
s.put("_wc20_tmp.py", "/root/mk_v2/_wc20_tmp.py")
s.put("_wc_audit.py", "/root/mk_v2/_wc_audit.py")
s.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc20_tmp.py", timeout=180)
R(c, "rm -f /root/mk_v2_runs/e1/witness_confirmation/audit.lock; ls /root/mk_v2_runs/e1/witness_confirmation/cells/*.json | wc -l")
print("=== new plan ===")
R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc_audit.py plan --n-a 50 --n-b 20 2>&1 | head -8", timeout=300)
cmd = ("cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u _wc_audit.py run "
       "--stage all --n-a 50 --n-b 20 "
       ">> /root/mk_v2_runs/e1/witness_confirmation/control_stdout.log 2>&1 "
       "< /dev/null & echo SPAWNED; exit 0")
R(c, cmd, timeout=30)
time.sleep(20)
R(c, "tail -5 /root/mk_v2_runs/e1/witness_confirmation/audit.log")
c.close()
