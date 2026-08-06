"""Find the sleep-60 source and per-case time breakdown."""
import _remote as R

c = R.connect()
print("### sleep usage in runner")
R.run(c, "grep -n 'sleep\\|cooldown\\|backoff\\|time.sleep' /root/mk_v2/scripts/run_fse_experiment.py | head -20", timeout=60)
print("### newest worker logs")
R.run(c, "ls -lat /root/mk_v2_runs/e3_campaign/lane_m_run/worker_logs/ | head -8", timeout=60)
R.run(c, "f=$(ls -t /root/mk_v2_runs/e3_campaign/lane_m_run/worker_logs/ | head -1); "
         "echo FILE=$f; tail -30 /root/mk_v2_runs/e3_campaign/lane_m_run/worker_logs/$f", timeout=60)
print("### runner stdout log (guard redirect)")
R.run(c, "grep -n 'lane_m' /root/mk_v2/guard_lane_m.sh | head; "
         "ls -lat /root/mk_v2_runs/e3_campaign/*.log | head -5", timeout=60)
c.close()
print("DIAG2_DONE")
