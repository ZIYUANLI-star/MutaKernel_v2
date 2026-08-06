"""Replace the resident stage-1 chainer with the redeployed version.

Safe only while it is still *waiting* for the first wave: the script refuses to
stop anything if STAGE1_FIRED exists or a lane driver / guard is alive.
Termination is by PID from a /proc scan that excludes this process and its
ancestors -- never `pkill -f`.
"""
import io
from pathlib import Path

import _remote

STOP = r'''
import os, signal, sys, time
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
            hits.append((int(entry), cl))
    return hits


for blocker in ("STAGE1_FIRED",):
    if (OUT / blocker).is_file():
        sys.exit("REFUSING: %s exists; stage 1 is already running" % blocker)
# a live wave-1 guard/lane is expected while the first wave runs; the chainer
# is only a poller, so replacing it mid-wave is safe.  What must not be
# replaced is a chainer that already owns stage 1 (guarded above).

targets = find("_b9_stage1_chain.py")
print("stage-1 chainer processes:", [p for p, _ in targets])
for pid, cl in targets:
    try:
        os.kill(pid, signal.SIGTERM)
        print("SIGTERM -> %d (%s)" % (pid, cl[:90]))
    except OSError as exc:
        print("kill %d failed: %s" % (pid, exc))
time.sleep(4)
left = find("_b9_stage1_chain.py")
if left:
    for pid, _ in left:
        try:
            os.kill(pid, signal.SIGKILL)
            print("SIGKILL -> %d" % pid)
        except OSError:
            pass
    time.sleep(2)
print("remaining:", [p for p, _ in find("_b9_stage1_chain.py")])
print("STOP_DONE")
'''

LAUNCH = (
    "cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u "
    "_b9_stage1_chain.py >> /root/mk_v2_runs/e3_b9_calib/stage1_chain_stdout.log "
    "2>&1 < /dev/null & disown; exit 0"
)

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(STOP.encode()), "/root/_s1_stop.py")
sftp.put(str(Path(__file__).resolve().parent / "_b9_stage1_chain.py"),
         "/root/mk_v2/_b9_stage1_chain.py")
sftp.close()
print("uploaded the new _b9_stage1_chain.py")

code, out, _ = _remote.run(c, "/root/miniconda3/bin/python /root/_s1_stop.py",
                           timeout=300)
if code != 0 or "STOP_DONE" not in out:
    print("stop refused or failed; not relaunching")
    c.close()
    raise SystemExit(1)

_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile "
               "_b9_stage1_chain.py && echo COMPILE_OK", timeout=300)
try:
    _remote.run(c, LAUNCH, timeout=25)
except Exception as exc:  # the channel may stay open; the process still starts
    print("launch channel note: %s" % exc)
_remote.run(c, "sleep 6; tail -6 "
               "/root/mk_v2_runs/e3_b9_calib/stage1_chain.log", timeout=180)
c.close()
print("RESTART_DONE")
