"""17:50 health check: throughput, GPU, processes, errors."""
import _remote as R

c = R.connect()
print("### processes")
R.run(c, "pgrep -af 'orchestrator|run_fse_experiment|guard_lane_m' | grep -v pgrep", timeout=60)
print("### ledger rows now + growth over 60s")
R.run(c, "wc -l < /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl; sleep 60; "
         "wc -l < /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl", timeout=150)
print("### GPU sampled during the same minute")
R.run(c, "for i in $(seq 1 6); do nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; sleep 3; done", timeout=60)
print("### recent 300 rows wall_ms stats + validation statuses")
R.run(c, "tail -300 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | "
         "/root/miniconda3/bin/python -c \"import sys,json,statistics,collections\n"
         "rows=[json.loads(l) for l in sys.stdin]\n"
         "ws=sorted(r.get('parent_wall_ms',0) for r in rows)\n"
         "st=collections.Counter(r.get('validation_status') for r in rows)\n"
         "print('n',len(ws),'median',round(ws[len(ws)//2]/1000,1),'s p90',round(ws[9*len(ws)//10]/1000,1),'s mean',round(statistics.mean(ws)/1000,1),'s')\n"
         "print('statuses:', dict(st))\"", timeout=60)
print("### errors in recent runner output?")
R.run(c, "tail -3 /root/mk_v2_runs/e3_campaign/lane_m_run.log; "
         "ls /root/mk_v2_runs/e3_campaign/ | grep -i 'DONE\\|BLOCKED' ; echo -; "
         "cd /root/mk_v2 && git status --porcelain | head -3; echo git_clean_check_done", timeout=60)
c.close()
print("CHECK_DONE")
