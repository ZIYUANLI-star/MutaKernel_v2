"""Full-chain audit probe 1: orchestrators, markers, lane M health."""
import _remote as R

c = R.connect()
print("### processes")
R.run(c, "pgrep -af 'orchestrator|run_fse_experiment|_mutant_worker|calib' | grep -v pgrep", timeout=60)
print("### GPU")
R.run(c, "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader", timeout=60)
print("### campaign markers")
R.run(c, "ls /root/mk_v2_runs/e3_campaign/ | grep -i 'DONE\\|BLOCKED\\|PAUSED'; echo ---; "
         "ls /root/mk_v2_runs/e3_campaign/wave15/ 2>/dev/null; echo ---; "
         "ls /root/mk_v2_runs/e3_campaign/wave2/ 2>/dev/null", timeout=60)
print("### lane M progress")
R.run(c, "wc -l /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl; "
         "ls /root/mk_v2_runs/e3_campaign/lane_m_run/ | head -20", timeout=60)
print("### lane M runner log tail")
R.run(c, "tail -15 /root/mk_v2_runs/e3_campaign/lane_m_run.log 2>/dev/null || "
         "ls /root/mk_v2_runs/e3_campaign/*.log", timeout=60)
print("### orchestrator logs")
R.run(c, "tail -5 /root/mk_v2_runs/e3_campaign/wave15/orchestrator.log 2>/dev/null; echo ---; "
         "tail -5 /root/mk_v2_runs/e3_campaign/wave2/orchestrator.log 2>/dev/null", timeout=60)
c.close()
print("AUDIT1_DONE")
