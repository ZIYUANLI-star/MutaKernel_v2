"""Quantify compile duplication and throughput."""
import _remote as R

c = R.connect()
print("### extensions dirs vs ledger rows")
R.run(c, "ls /root/mk_v2_runs/e3_campaign/lane_m_run/torch_extensions/ | wc -l; "
         "wc -l < /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl", timeout=60)
print("### how TORCH_EXTENSIONS_DIR is set per case")
R.run(c, "grep -n 'TORCH_EXTENSIONS\\|extensions' /root/mk_v2/scripts/run_fse_experiment.py | head -10", timeout=60)
print("### timing fields available in one observation")
R.run(c, "tail -1 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | "
         "/root/miniconda3/bin/python -c \"import sys,json; r=json.loads(sys.stdin.read()); "
         "print(sorted(r.keys()))\"", timeout=60)
print("### subjects completed so far + throughput")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "subs=set(); n=0\n"
         "for l in open('/root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl'):\n"
         "    if l.strip():\n"
         "        n+=1; subs.add(json.loads(l).get('subject_id'))\n"
         "print('rows', n, 'distinct subjects', len(subs))\n"
         "plan=json.load(open('/root/mk_v2_runs/e3_campaign/wave1_lane_m_plan_v2.json'))\n"
         "cases=plan.get('cases') or plan.get('case_count')\n"
         "print('plan cases:', len(cases) if isinstance(cases,list) else cases)\n"
         "print('plan subjects:', len({c['subject_id'] for c in cases}) if isinstance(cases,list) else '?')\n"
         "EOF", timeout=300)
print("### wall_ms distribution of recent 200 rows")
R.run(c, "tail -200 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | "
         "/root/miniconda3/bin/python -c \"import sys,json\n"
         "ws=[json.loads(l).get('parent_wall_ms',0) for l in sys.stdin]\n"
         "ws.sort()\n"
         "import statistics\n"
         "print('n',len(ws),'median',round(ws[len(ws)//2]/1000,1),'s  p10',round(ws[len(ws)//10]/1000,1),'s  p90',round(ws[9*len(ws)//10]/1000,1),'s  mean',round(statistics.mean(ws)/1000,1),'s')\"",
      timeout=60)
c.close()
print("DIAG3_DONE")
