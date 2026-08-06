"""Retire the old run manifest (v1->v2 precedent) and verify the runner resumes."""
import time
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()
R.run(c, f"mv {OUT}/lane_m_run/run_manifest.json {OUT}/lane_m_run/run_manifest_v2_pre_cachefix_retired.json && "
         f"ls {OUT}/lane_m_run/run_manifest*", timeout=60)
print("### wait for guard restart cycle (~100s)")
time.sleep(100)
R.run(c, "pgrep -af run_fse_experiment | grep -v pgrep || echo NOT_RUNNING", timeout=60)
R.run(c, f"tail -2 {OUT}/lane_m_run.log; tail -3 {OUT}/guard_lane_m.log", timeout=60)
R.run(c, f"ls -la {OUT}/lane_m_run/run_manifest.json 2>/dev/null; "
         f"wc -l < {OUT}/lane_m_run/observations.jsonl", timeout=60)
c.close()
print("MANIFEST_FIX_DONE")
