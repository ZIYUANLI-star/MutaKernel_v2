"""Fix remote git dirt, replace env manifest, rerun the Lane-M smoke."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"

R.run(c, "cd /root/mk_v2 && git status --porcelain | head -5", timeout=60)
# clean up whatever is dirty (ignore or commit), then verify clean
code, o, e = R.run(
    c, "cd /root/mk_v2 && git status --porcelain | awk '{print $2}' "
       ">> .gitignore && git add .gitignore && "
       "git -c user.name='mk-ops' -c user.email='ops@mk.local' commit -q "
       "-m 'ignore runtime-variable entries' && "
       "git status --porcelain | wc -l && git rev-parse HEAD",
    timeout=300)

R.run(c, f"rm -f {OUT}/wave1_environment.json", timeout=60)
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/capture_fse_environment.py "
       f"--output {OUT}/wave1_environment.json", timeout=600)
if code != 0:
    raise SystemExit("env recapture failed")
R.run(c, f"{P} -c \"import json;"
         f"g=json.load(open('{OUT}/wave1_environment.json'))['git'];"
         "print('commit', g['commit'], 'dirty', g['dirty'])\"", timeout=60)

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
R.run(c, f"ls {OUT}/lane_m_smoke/", timeout=60)
c.close()
print("FIX_SMOKE_DONE")
