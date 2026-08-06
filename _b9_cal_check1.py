# -*- coding: utf-8 -*-
"""Check whether guard/lanes actually started after the channel timeout."""
import _remote as R

c = R.connect()
R.run(c, "pgrep -af 'guard_b9.sh|_b9_calib_driver' ; echo ---; "
         "tail -8 /root/mk_v2_runs/e3_b9_calib/guard_b9.log 2>&1; echo ---; "
         "for L in 0 1 2 3; do echo lane$L:; tail -2 /root/mk_v2_runs/e3_b9_calib/lane$L.log 2>&1; done; "
         "echo ---; nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader",
      timeout=60)
c.close()
print("CHECK1_DONE")
