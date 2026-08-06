"""Deploy + launch a keepalive for the chain trigger, then verify both are up."""
import io
import socket
import time

import _remote

KEEPALIVE = r'''#!/bin/bash
# Relaunch the B9 chain trigger if it disappears (deployed to
# /root/mk_v2_runs/e3_b9_calib/keepalive_chain.sh).
#
# Safe to run blindly: the trigger takes an flock, so a duplicate launch exits
# immediately without starting a second wave.  The loop retires itself once the
# trigger has written CHAIN_TRIGGER_EXIT, so a finished wave is never restarted.
# Liveness is a /proc scan inside python (never `pgrep -f`, which would match
# this script's own command line).
OUT=/root/mk_v2_runs/e3_b9_calib
PY=/root/miniconda3/bin/python
LOG=$OUT/keepalive_chain.log

echo "$(date '+%F %T') keepalive start pid=$$" >> "$LOG"
while true; do
  if [ -f "$OUT/CHAIN_TRIGGER_EXIT" ]; then
    echo "$(date '+%F %T') trigger recorded its exit -> keepalive retires" >> "$LOG"
    break
  fi
  if ! "$PY" /root/mk_v2/_b9_chain_alive.py; then
    echo "$(date '+%F %T') chain trigger absent -> relaunch" >> "$LOG"
    cd /root/mk_v2 && setsid "$PY" -u _b9_chain_trigger.py \
      >> "$OUT/chain_trigger_stdout.log" 2>&1 < /dev/null &
  fi
  sleep 300
done
'''

ALIVE = r'''#!/usr/bin/env python3
"""Exit 0 if a chain trigger process is alive, 1 otherwise (for the keepalive)."""
import sys

sys.path.insert(0, "/root/mk_v2")
import _b9_chain_trigger as trigger

sys.exit(0 if trigger.find_processes("_b9_chain_trigger.py") else 1)
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(KEEPALIVE.encode()),
           "/root/mk_v2_runs/e3_b9_calib/keepalive_chain.sh")
sftp.putfo(io.BytesIO(ALIVE.encode()), "/root/mk_v2/_b9_chain_alive.py")
sftp.close()
_remote.run(c, "chmod +x /root/mk_v2_runs/e3_b9_calib/keepalive_chain.sh; "
               "/root/miniconda3/bin/python /root/mk_v2/_b9_chain_alive.py; "
               "echo ALIVE_CHECK_EXIT=$?", timeout=120)
c.close()

print("\n#### launch keepalive (channel may hang; verified afterwards)")
try:
    c = _remote.connect()
    _remote.run(c, "cd /root/mk_v2_runs/e3_b9_calib && setsid bash keepalive_chain.sh "
                   "> /dev/null 2>&1 < /dev/null & echo SPAWNED; exit 0", timeout=25)
    c.close()
except (socket.timeout, Exception) as exc:  # noqa: BLE001 - expected detach behaviour
    print("launch channel returned/timed out as expected: %s" % type(exc).__name__)

time.sleep(20)
c = _remote.connect()
for cmd in [
    "cat /root/mk_v2_runs/e3_b9_calib/keepalive_chain.log",
    "/root/miniconda3/bin/python -c \"import sys; sys.path.insert(0,'/root/mk_v2');"
    "import _b9_chain_trigger as t;"
    "print('trigger:', t.find_processes('_b9_chain_trigger.py'));"
    "print('keepalive:', t.find_processes('keepalive_chain.sh'))\"",
]:
    print("\n#### " + cmd[:70])
    _remote.run(c, cmd, timeout=180)
c.close()
print("\nH20_DONE")
