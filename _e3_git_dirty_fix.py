"""Find dirt, commit it, recapture env, verify runner starts."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"

R.run(c, "cd /root/mk_v2 && git status --porcelain | head -10", timeout=60)
R.run(c, f"ls {OUT}/lane_m_run/ 2>/dev/null", timeout=60)
code, o, e = R.run(
    c, "cd /root/mk_v2 && git add -A && "
       "git -c user.name='mk-ops' -c user.email='ops@mk.local' commit -q "
       "-m 'campaign assets: e3 wave1 matrix + gitignore' && "
       "git status --porcelain | wc -l && git rev-parse HEAD", timeout=120)
R.run(c, f"rm -f {OUT}/wave1_environment.json && cd /root/mk_v2 && "
         f"PATH=/usr/local/cuda/bin:$PATH {P} -u "
         "scripts/capture_fse_environment.py "
         f"--output {OUT}/wave1_environment.json", timeout=600)
R.run(c, f"{P} -c \"import json;"
         f"g=json.load(open('{OUT}/wave1_environment.json'));"
         "print('commit', g['git']['commit'][:12], 'dirty', g['git']['dirty'],"
         " 'nvcc', g['nvcc']['status'])\"", timeout=60)
# guard will retry within 60 s; wait and verify
R.run(c, "sleep 90; pgrep -af run_fse_experiment | head -2; "
         f"tail -3 {OUT}/lane_m_run.log; "
         f"tail -3 {OUT}/guard_lane_m.log", timeout=180)
c.close()
print("DIRTY_FIX_DONE")
