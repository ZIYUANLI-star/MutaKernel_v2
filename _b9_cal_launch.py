# -*- coding: utf-8 -*-
"""Launch the B9 calibration guard (which starts the 4 lane drivers), then
verify processes + first log lines."""
import time

import _remote as R

c = R.connect()
print("### start guard (spawns lanes)")
R.run(c, "cd /root/mk_v2_runs/e3_b9_calib && nohup bash guard_b9.sh "
         "> /dev/null 2>&1 & echo GUARD_SPAWNED $!", timeout=15)
time.sleep(20)
print("### processes")
R.run(c, "pgrep -af 'guard_b9.sh|_b9_calib_driver' | head", timeout=30)
print("### lane logs")
R.run(c, "for L in 0 1 2 3; do echo --lane$L--; "
         "tail -3 /root/mk_v2_runs/e3_b9_calib/lane$L.log 2>&1; done",
      timeout=30)
print("### guard log")
R.run(c, "tail -6 /root/mk_v2_runs/e3_b9_calib/guard_b9.log", timeout=30)
print("### gpu")
R.run(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader",
      timeout=30)
c.close()
print("B9_LAUNCH_DONE")
