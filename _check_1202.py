"""Post-prewarm-wiring health check."""
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()
print("### A. all processes")
R.run(c, "pgrep -af 'orchestrator|run_fse_experiment|guard_lane_m|prewarm' | grep -v grep", timeout=60)
print("### B. prewarm final tally")
R.run(c, f"tail -1 {OUT}/prewarm_run.log; "
         f"/root/miniconda3/bin/python -c \"import json,collections\n"
         f"st=collections.Counter(json.loads(l)['status'] for l in open('{OUT}/lane_m_run/prewarm_log.jsonl'))\n"
         f"print('prewarm statuses:', dict(st))\"; "
         f"ls {OUT}/lane_m_run/torch_extensions/ | wc -l", timeout=60)
print("### C. runner still appending? (2-min window)")
R.run(c, f"a=$(wc -l < {OUT}/lane_m_run/observations.jsonl); sleep 120; "
         f"b=$(wc -l < {OUT}/lane_m_run/observations.jsonl); "
         f"echo rows=$b delta_2min=$((b-a))", timeout=200)
print("### D. orchestrator logs + errors + git")
R.run(c, f"tail -1 {OUT}/wave15/orchestrator.log; tail -1 {OUT}/wave2/orchestrator.log; "
         f"tail -2 {OUT}/lane_m_run.log; tail -1 {OUT}/guard_lane_m.log; "
         f"cd /root/mk_v2 && git status --porcelain | wc -l; "
         f"nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
         f"uptime | awk -F'load average:' '{{print $2}}'", timeout=60)
c.close()
print("CHECK1202_DONE")
