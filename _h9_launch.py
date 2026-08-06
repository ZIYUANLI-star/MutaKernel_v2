"""Launch the chain trigger detached, then verify it is in the waiting state."""
import time

import _remote

LAUNCH = ("cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u "
          "_b9_chain_trigger.py "
          ">> /root/mk_v2_runs/e3_b9_calib/chain_trigger_stdout.log 2>&1 "
          "< /dev/null & echo SPAWNED; exit 0")

c = _remote.connect()
print("#### launch")
_remote.run(c, LAUNCH, timeout=120)
c.close()

print("\n#### waiting 75s for the first poll cycle")
time.sleep(75)

c = _remote.connect()
for cmd in [
    "cat /root/mk_v2_runs/e3_b9_calib/chain_trigger.log",
    "cat /root/mk_v2_runs/e3_b9_calib/chain_trigger.lock",
    "ls -la /root/mk_v2_runs/e3_b9_calib/CHAIN_TRIGGER_FIRED /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN 2>&1",
    "/root/miniconda3/bin/python /root/_h1_scan.py",
]:
    print("\n#### " + cmd[:80])
    _remote.run(c, cmd, timeout=180)

print("\n#### idempotency: launch a second instance, it must refuse")
_remote.run(c, LAUNCH, timeout=120)
c.close()
time.sleep(20)
c = _remote.connect()
print("\n#### log tail after the second launch")
_remote.run(c, "tail -8 /root/mk_v2_runs/e3_b9_calib/chain_trigger.log", timeout=120)
print("\n#### chain trigger processes (must be exactly one)")
_remote.run(c, "/root/miniconda3/bin/python -c \"import sys; sys.path.insert(0,'/root/mk_v2');"
               "import _b9_chain_trigger as t;"
               "print(t.find_processes('_b9_chain_trigger.py'))\"", timeout=120)
c.close()
print("\nH9_DONE")
