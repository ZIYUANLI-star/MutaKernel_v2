"""Second ignition check after env fix."""
import _remote as R

c = R.connect()
OUT = "/root/mk_v2_runs/e3_campaign"
R.run(c, "sleep 100; pgrep -af 'run_fse_experiment' | grep -v pgrep | head -2; "
         "echo ---; "
         f"tail -2 {OUT}/lane_m_run.log; echo ---; "
         f"tail -3 {OUT}/guard_lane_m.log; echo ---; "
         f"wc -l {OUT}/lane_m_run/observations.jsonl 2>/dev/null; "
         "nvidia-smi --query-gpu=utilization.gpu,memory.used "
         "--format=csv,noheader", timeout=240)
c.close()
print("CHECK2_DONE")
