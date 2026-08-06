"""Step 9: final verification of early-stop switchover."""
import time
import _remote as R

c = R.connect()
time.sleep(90)
R.run(c, "pgrep -af 'run_fse_[e]xperiment' >/dev/null && echo RUNNER_ALIVE; "
         "ls -la /root/mk_v2_runs/e3_campaign/lane_m_run/run_manifest.json 2>/dev/null; "
         "wc -l /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl; "
         "pgrep -af '_candidate_[w]orker' | head -1; "
         "tail -n 1 /root/mk_v2_runs/e3_campaign/lane_m_run.log; "
         "tail -n 1 /root/mk_v2_runs/e3_campaign/guard_lane_m.log", timeout=60)
print("### manifest v2 config check")
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import json;"
         "d=json.load(open('/root/mk_v2_runs/e3_campaign/lane_m_run/run_manifest.json'));"
         "c=d.get('config',{});r=c.get('runner',c);"
         "print('early_stop:', r.get('early_stop_on_fail'));"
         "print('git:', d.get('git',{}).get('commit','')[:8], "
         "'dirty:', d.get('git',{}).get('dirty'))\" 2>&1 | head -5", timeout=60)
c.close()
print("FINAL_VERIFY_DONE")
