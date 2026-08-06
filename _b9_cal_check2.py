# -*- coding: utf-8 -*-
"""Inspect the L1_P3 run_error + overall early health."""
import _remote as R

c = R.connect()
R.run(c, "tail -25 '/root/mk_v2_runs/e3_b9_calib/units/L1_P3__float32/run.log'",
      timeout=30)
print("### calibration rows so far")
R.run(c, "cat /root/mk_v2_runs/e3_b9_calib/calibration_lane*.jsonl 2>/dev/null",
      timeout=30)
print("### gpu/mem")
R.run(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
         "free -g | sed -n 2p", timeout=30)
c.close()
print("CHECK2_DONE")
