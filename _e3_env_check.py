"""Check env manifest git fields + remote repo state + runner's git gate."""
import _remote as R

c = R.connect()
R.run(c, "cat /root/mk_v2_runs/e3_campaign/wave1_environment.json", timeout=60)
R.run(c, "cd /root/mk_v2 && git rev-parse HEAD 2>&1 | head -2; "
         "git status --porcelain 2>/dev/null | wc -l", timeout=60)
R.run(c, "grep -n 'no Git commit\\|allow_dirty\\|allow-dirty\\|git' "
         "/root/mk_v2/scripts/run_fse_experiment.py | head -20", timeout=60)
c.close()
print("ENV_CHECK_DONE")
