"""Git-init the deployed remote tree (provenance commit), re-capture env, smoke.

The FSE runner requires environment.git.commit and re-verifies the live commit
at every start. The remote /root/mk_v2 is a deployed copy without git; we pin
it with a local provenance commit of the exact tree state (runs live outside
in /root/mk_v2_runs, so the repo stays stable during the campaign).
"""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"

gitignore = "\n".join([
    "__pycache__/", "*.pyc", "*.pyo", ".pytest_cache/", "*.so",
    "_*.py",  # ops one-off scripts dropped into the tree root
    "", 
])
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/.gitignore", "w") as fh:
    fh.write(gitignore)
sftp.close()

code, o, e = R.run(
    c, "cd /root/mk_v2 && git init -q 2>&1 && "
       "git add -A 2>&1 | tail -2 && "
       "git -c user.name='mk-ops' -c user.email='ops@mk.local' commit -q "
       "-m 'provenance pin: deployed tree at E3 wave-1 ignition (2026-08-02)' "
       "&& git rev-parse HEAD && git status --porcelain | wc -l",
    timeout=900)
if code != 0:
    raise SystemExit("git provenance pin failed")

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
print("GIT_SMOKE_DONE")
