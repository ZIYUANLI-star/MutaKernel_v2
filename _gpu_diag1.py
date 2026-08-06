"""GPU idle diagnosis: sample GPU over 60s, measure ledger throughput, inspect worker state."""
import time
import _remote as R

c = R.connect()
print("### GPU sampled 12x over 60s")
R.run(c, "for i in $(seq 1 12); do nvidia-smi --query-gpu=utilization.gpu,memory.used "
         "--format=csv,noheader; sleep 5; done", timeout=120)
print("### ledger growth over the same window")
R.run(c, "wc -l /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl; sleep 30; "
         "wc -l /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl", timeout=90)
print("### runner + children process tree")
R.run(c, "ps --forest -o pid,etime,pcpu,pmem,stat,cmd -g $(ps -o pgid= -p 572643 | tr -d ' ') | head -25", timeout=60)
print("### last ledger rows: subject + timing")
R.run(c, "tail -5 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | "
         "/root/miniconda3/bin/python -c \"import sys,json\n"
         "for l in sys.stdin:\n"
         "    r=json.loads(l)\n"
         "    keep={k:r[k] for k in r if any(t in k.lower() for t in ('subject','case','status','outcome','wall','elapsed','time','strategy'))}\n"
         "    print(json.dumps(keep)[:400])\"", timeout=60)
c.close()
print("DIAG1_DONE")
