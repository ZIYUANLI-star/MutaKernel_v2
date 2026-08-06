"""Drop embedded-repo gitlinks from the index, clean tree, recapture, smoke."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"

code, o, e = R.run(
    c, "cd /root/mk_v2 && "
       "git rm -q --cached -r external/C6_gpuemu/gpuemu "
       "external/C6_gpuemu/gpuemu-corpus && "
       "printf 'external/C6_gpuemu/gpuemu/\\nexternal/C6_gpuemu/gpuemu-corpus/\\n' "
       ">> .gitignore && git add .gitignore && "
       "git -c user.name='mk-ops' -c user.email='ops@mk.local' commit -q "
       "-m 'untrack embedded corpus repos (content unchanged on disk)' && "
       "git status --porcelain | wc -l && git rev-parse HEAD",
    timeout=300)
if code != 0:
    raise SystemExit("git cleanup failed")

R.run(c, f"rm -f {OUT}/wave1_environment.json", timeout=60)
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/capture_fse_environment.py "
       f"--output {OUT}/wave1_environment.json", timeout=600)
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
       f"--max-tests 12 2>&1 | tail -30",
    timeout=1800)
print("SMOKE_EXIT", code)
R.run(c, f"ls {OUT}/lane_m_smoke/ && "
         f"tail -3 {OUT}/lane_m_smoke/*.jsonl 2>/dev/null | head -40", timeout=60)
c.close()
print("FIX2_SMOKE_DONE")
