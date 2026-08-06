"""Restart the supervisor on the new code, retire the trigger, start its keepalive."""
import io

import _remote

STOP_SUPERVISOR = r'''
import os, signal, sys, time
from pathlib import Path
sys.path.insert(0, "/root/mk_v2")
import _b9_brake as brake

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
if (OUT / "STAGE1_FIRED").is_file():
    sys.exit("REFUSING: STAGE1_FIRED exists; not replacing a supervisor that "
             "owns a running stage 1")
targets = brake.find_processes("_b9_stage1_chain.py")
print("supervisors:", [p for p, _ in targets])
for pid, cmdline in targets:
    if "_b9_stage1_chain.py" in cmdline:
        try:
            os.kill(pid, signal.SIGTERM)
            print("  SIGTERM -> %d" % pid)
        except OSError as exc:
            print("  kill %d failed: %s" % (pid, exc))
time.sleep(4)
for pid, cmdline in brake.find_processes("_b9_stage1_chain.py"):
    if "_b9_stage1_chain.py" in cmdline:
        os.kill(pid, signal.SIGKILL)
        print("  SIGKILL -> %d" % pid)
time.sleep(2)
print("remaining:", brake.find_processes("_b9_stage1_chain.py") or "none")
print("brake holders (must be unchanged):", sorted(o for o, _ in brake.holders()))
print("STOP_DONE")
'''

LAUNCH_SUP = ("cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u "
              "_b9_stage1_chain.py >> /root/mk_v2_runs/e3_b9_calib/"
              "stage1_chain_stdout.log 2>&1 < /dev/null & disown; exit 0")
LAUNCH_KA = ("cd /root/mk_v2_runs/e3_b9_calib && setsid bash keepalive_stage1.sh "
             "> /dev/null 2>&1 < /dev/null & disown; exit 0")

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(STOP_SUPERVISOR.encode()), "/root/_stop_supervisor.py")
sftp.close()

print("#### 1. replace the supervisor with the rewired build")
code, out, _ = _remote.run(c, "/root/miniconda3/bin/python /root/_stop_supervisor.py",
                           timeout=300)
if "STOP_DONE" not in out:
    print("stop refused; aborting")
    c.close()
    raise SystemExit(1)
try:
    _remote.run(c, LAUNCH_SUP, timeout=25)
except Exception as exc:  # noqa: BLE001 - detach may keep the channel open
    print("launch channel note: %s" % type(exc).__name__)
_remote.run(c, "sleep 10; tail -8 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log",
            timeout=180)

print("\n#### 2-4. retire the trigger and its keepalive")
_remote.run(c, "/root/miniconda3/bin/python /root/_retire_trigger.py", timeout=600)

print("\n#### 5. start the supervisor's keepalive")
try:
    _remote.run(c, LAUNCH_KA, timeout=25)
except Exception as exc:  # noqa: BLE001
    print("launch channel note: %s" % type(exc).__name__)
_remote.run(c, "sleep 8; cat /root/mk_v2_runs/e3_b9_calib/keepalive_stage1.log",
            timeout=180)
c.close()
print("\nRETIRE_GO_DONE")
