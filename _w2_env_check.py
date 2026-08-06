import _remote as R

c = R.connect()
print("### wave15 orchestrator constants + s8 out dir")
R.run(c, "grep -n 'ENV\\|environment\\|lane_c6\\|SUBJECTS\\|MATRIX' /root/mk_v2_ops/wave15_orchestrator.py | head -25",
      timeout=60)
print("### plan_b9_port signature/body head")
R.run(c, "grep -n 'def plan_b9_port' -A 30 /root/mk_v2/scripts/run_e3_external.py",
      timeout=60)
print("### files exist?")
R.run(c, "ls -la /root/mk_v2_runs/e3_campaign/wave15/wave15_environment_v3.json "
         "/root/mk_v2_runs/e3_campaign/wave2_subject_manifest.json "
         "/root/mk_v2_runs/e3_campaign/wave2_lane_m_plan.json "
         "/root/mk_v2_runs/e3_campaign/wave2_mdir_plan.json 2>&1",
      timeout=60)
c.close()
print("DONE")
