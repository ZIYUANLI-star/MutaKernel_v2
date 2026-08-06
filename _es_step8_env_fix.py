"""Step 8: recapture env v2 with CUDA PATH (matching guard's runner env)."""
import time
import _remote as R

c = R.connect()
R.run(c, "rm -f /root/mk_v2_runs/e3_campaign/wave1_environment_v2.json && "
         "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
         "/root/miniconda3/bin/python scripts/capture_fse_environment.py "
         "--output /root/mk_v2_runs/e3_campaign/wave1_environment_v2.json && "
         "/root/miniconda3/bin/python -c \"import json;"
         "d=json.load(open('/root/mk_v2_runs/e3_campaign/wave1_environment_v2.json'));"
         "print('git:', d['git']['commit'][:8], 'dirty:', d['git']['dirty']);"
         "print('nvcc key present:', 'nvcc' in json.dumps(d))\"", timeout=300)
print("### wait for guard retry cycle (~100s)")
time.sleep(110)
R.run(c, "pgrep -af 'run_fse_[e]xperiment' | head -2 || echo RUNNER_NOT_UP; "
         "tail -n 2 /root/mk_v2_runs/e3_campaign/lane_m_run.log; "
         "tail -n 2 /root/mk_v2_runs/e3_campaign/guard_lane_m.log", timeout=60)
c.close()
print("ENV_FIX_DONE")
