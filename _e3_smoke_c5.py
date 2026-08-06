"""C5 smoke in its own output dir."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"

code, o, e = R.run(
    c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
       f"{P} -u scripts/run_fse_experiment.py "
       f"--plan {OUT}/wave1_lane_m_plan_v2.json "
       f"--subjects {OUT}/wave1_subject_manifest_v2.json "
       f"--environment {OUT}/wave1_environment.json "
       f"--artifact-root / "
       f"--output-dir {OUT}/lane_m_smoke_c5 "
       f"--run-id lane-m-smoke-c5 "
       f"--device cuda "
       f"--subject C5__KB_L1_P100__868dac70cc5d9646 "
       f"--max-tests 8 2>&1 | tail -6",
    timeout=2400)
print("c5 EXIT", code)
code, o, e = R.run(
    c, f"{P} -c \"import json,collections;"
       f"rows=[json.loads(l) for l in open('{OUT}/lane_m_smoke_c5/observations.jsonl')];"
       "print(collections.Counter(r['validation_status'] for r in rows));"
       "print(collections.Counter(r['worker_result'].get('phase')"
       " for r in rows if r['validation_status']!='pass'))\"", timeout=60)
c.close()
print("SMOKE_C5_DONE")
