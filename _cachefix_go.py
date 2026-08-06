"""Deploy the per-subject cache namespace fix for Lane M (documented restart).

Steps: disk check -> patch runner + guard -> commit -> capture env v2.1 ->
backup run manifest -> restart guard+runner -> verify resume.
"""
import time
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()

print("### 0. disk space")
R.run(c, "df -h /root | tail -1", timeout=60)

print("### 1. patch runner (line 863 area)")
code, o, _ = R.run(c, "grep -n 'cache_namespace=strategy_id' /root/mk_v2/scripts/run_fse_experiment.py", timeout=60)
assert "cache_namespace=strategy_id" in o, "call site not found"
R.run(c, "sed -i 's/cache_namespace=strategy_id,/cache_namespace=raw_subject[\"subject_sha256\"],/' "
         "/root/mk_v2/scripts/run_fse_experiment.py && "
         "grep -n 'cache_namespace=raw_subject' /root/mk_v2/scripts/run_fse_experiment.py", timeout=60)
R.run(c, "/root/miniconda3/bin/python -m py_compile /root/mk_v2/scripts/run_fse_experiment.py && echo RUNNER_COMPILE_OK", timeout=120)

print("### 2. patch guard to env manifest v2.1")
R.run(c, "sed -i 's|wave1_environment_v2.json|wave1_environment_v2_1.json|' /root/mk_v2/guard_lane_m.sh && "
         "grep -n 'environment' /root/mk_v2/guard_lane_m.sh", timeout=60)

print("### 3. commit")
R.run(c, "cd /root/mk_v2 && git add scripts/run_fse_experiment.py guard_lane_m.sh && "
         "git -c user.name=mk-ops -c user.email=ops@mk.local commit -m "
         "'lane-m: per-subject torch-extension cache namespace (fixes cross-candidate "
         "compile thrashing, verdict semantics unchanged); guard -> env manifest v2.1' "
         "&& git log --oneline -1 && git status --porcelain && echo TREE_CLEAN", timeout=120)

print("### 4. capture env manifest v2.1 (post-commit, cuda on PATH)")
R.run(c, f"cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH /root/miniconda3/bin/python "
         f"scripts/capture_fse_environment.py --output {OUT}/wave1_environment_v2_1.json && "
         f"/root/miniconda3/bin/python -c \"import json; m=json.load(open('{OUT}/wave1_environment_v2_1.json')); "
         f"print('commit', m['git']['commit'][:8], 'dirty', m['git']['dirty'])\"", timeout=300)

print("### 5. backup current run manifest")
R.run(c, f"cp {OUT}/lane_m_run/run_manifest.json {OUT}/lane_m_run/run_manifest_v2_pre_cachefix.json && "
         f"echo BACKUP_OK", timeout=60)

print("### 6. stop old guard + runner")
R.run(c, "kill 572431 2>/dev/null; sleep 1; kill 572643 2>/dev/null; sleep 3; "
         "pgrep -af 'guard_lane_m|run_fse_experiment' | grep -v pgrep || echo ALL_STOPPED", timeout=60)

print("### 7. start new guard")
R.run(c, "cd /root/mk_v2 && (setsid nohup ./guard_lane_m.sh > /dev/null 2>&1 &); sleep 2; "
         "pgrep -af guard_lane_m | grep -v pgrep", timeout=60)

print("### 8. wait for runner start + env check")
time.sleep(45)
R.run(c, "pgrep -af run_fse_experiment | grep -v pgrep; "
         f"tail -3 {OUT}/lane_m_run.log; "
         f"tail -3 {OUT}/guard_lane_m.log", timeout=60)
c.close()
print("CACHEFIX_DEPLOYED")
