"""Deep dive: extensions namespace lifecycle + inconclusive reasons."""
import _remote as R

c = R.connect()
print("### runner code: worker env, namespace, cleanup (lines 295-360)")
R.run(c, "sed -n '295,360p' /root/mk_v2/scripts/run_fse_experiment.py", timeout=60)
print("### torch_extensions contents now, twice 60s apart")
R.run(c, "ls /root/mk_v2_runs/e3_campaign/lane_m_run/torch_extensions/; echo ---; sleep 60; "
         "ls /root/mk_v2_runs/e3_campaign/lane_m_run/torch_extensions/", timeout=150)
print("### one recent inconclusive row: worker_result")
R.run(c, "tail -300 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | "
         "/root/miniconda3/bin/python -c \"import sys,json\n"
         "for l in sys.stdin:\n"
         "    r=json.loads(l)\n"
         "    if r.get('validation_status')=='inconclusive':\n"
         "        print(r['subject_id'], r['strategy_name'])\n"
         "        print(json.dumps(r.get('worker_result'))[:1200])\n"
         "        break\"", timeout=60)
c.close()
print("DEEP1_DONE")
