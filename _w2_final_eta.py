import _remote as R

c = R.connect()
R.run(c, "wc -l /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl; "
         "ls /root/mk_v2_runs/e3_campaign/LANE_M_DONE 2>/dev/null && echo M_DONE; "
         "tail -2 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | "
         "/root/miniconda3/bin/python -c \"import sys,json;"
         "rows=[json.loads(l) for l in sys.stdin];"
         "print([r.get('finished_at') or r.get('timestamp') for r in rows])\"",
      timeout=120)
c.close()
print("DONE")
