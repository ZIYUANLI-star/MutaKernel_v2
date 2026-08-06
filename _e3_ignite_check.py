"""Check whether guard + runner actually started."""
import _remote as R

c = R.connect()
OUT = "/root/mk_v2_runs/e3_campaign"
R.run(c, "pgrep -af guard_lane_m | head -3; echo ---; "
         "pgrep -af run_fse_experiment | head -3", timeout=60)
R.run(c, f"tail -6 {OUT}/guard_lane_m.log 2>/dev/null; echo ---; "
         f"tail -4 {OUT}/lane_m_run.log 2>/dev/null; echo ---; "
         f"wc -l {OUT}/lane_m_run/observations.jsonl 2>/dev/null", timeout=60)
R.run(c, "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader",
      timeout=60)
c.close()
print("IGNITE_CHECK_DONE")
