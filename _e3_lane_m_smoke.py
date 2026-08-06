"""Lane-M GPU smoke: one subject, ~12 cases, verify observations + evidence."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"

code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/run_fse_experiment.py "
       f"--plan {OUT}/wave1_lane_m_plan.json "
       f"--subjects {OUT}/wave1_subject_manifest.json "
       f"--environment {OUT}/wave1_environment.json "
       f"--artifact-root / "
       f"--output-dir {OUT}/lane_m_smoke "
       f"--run-id lane-m-smoke-1 "
       f"--device cuda "
       f"--subject C3__KB_L1_P1__018d33522a22175e "
       f"--max-tests 12 2>&1 | tail -25",
    timeout=1800)
print("SMOKE_EXIT", code)
R.run(c, f"ls -la {OUT}/lane_m_smoke/ 2>/dev/null | head -20", timeout=60)
R.run(c, f"head -c 1500 {OUT}/lane_m_smoke/*observations* 2>/dev/null | head -30",
      timeout=60)
c.close()
print("LANE_M_SMOKE_DONE")
