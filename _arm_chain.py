"""Build the full Lane D plan (CPU) and arm the wave-1.5 orchestrator."""
import _remote as R

c = R.connect()

print("### 1. build full Lane D (M-dir) plan, 653 subjects")
R.run(c, "cd /root/mk_v2_ops && /root/miniconda3/bin/python "
         "build_wave15_lane_plans.py mdir-plan "
         "--subjects /root/mk_v2_runs/e3_campaign/wave1_subject_manifest_v2.json "
         "--map /root/mk_v2_runs/e1/fault_to_stress_map.json "
         "--artifact-root / "
         "--out /root/mk_v2_runs/e3_campaign/wave15/lane_d_plan.json",
      timeout=3600)

print("### 2. arm orchestrator (detached)")
R.run(c, "cd /root/mk_v2_ops && setsid nohup /root/miniconda3/bin/python -u "
         "wave15_orchestrator.py "
         ">> /root/mk_v2_runs/e3_campaign/wave15/orchestrator_stdout.log 2>&1 & "
         "sleep 3; ps aux | grep wave15_orchestrator | grep -v grep",
      timeout=60)

print("### 3. first heartbeat")
R.run(c, "sleep 5; tail -5 /root/mk_v2_runs/e3_campaign/wave15/orchestrator.log "
         "2>/dev/null; cat /root/mk_v2_runs/e3_campaign/wave15/orchestrator.pid",
      timeout=60)
c.close()
print("ARM_DONE")
