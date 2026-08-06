"""Lane-M GPU smoke v2: one C3 subject (compiles CUDA) + one C5 subject."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"

for tag, subj, n in (
        ("c3", "C3__KB_L1_P1__018d33522a22175e", 8),
        ("c5", None, 8)):
    if subj is None:
        code, o, e = R.run(
            c, f"{P} -c \"import json;"
               f"m=json.load(open('{OUT}/wave1_subject_manifest_v2.json'));"
               "s=[x['subject_id'] for x in m['subjects']"
               " if x['subject_id'].startswith('C5')];print(s[0])\"", timeout=60)
        subj = o.strip().splitlines()[-1]
    print(f"#### smoke {tag}: {subj}")
    code, o, e = R.run(
        c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
           f"{P} -u scripts/run_fse_experiment.py "
           f"--plan {OUT}/wave1_lane_m_plan_v2.json "
           f"--subjects {OUT}/wave1_subject_manifest_v2.json "
           f"--environment {OUT}/wave1_environment.json "
           f"--artifact-root / "
           f"--output-dir {OUT}/lane_m_smoke_v2 "
           f"--run-id lane-m-smoke-2 "
           f"--device cuda "
           f"--subject {subj} "
           f"--max-tests {n} 2>&1 | tail -6",
        timeout=2400)
    print(f"{tag} EXIT", code)

# outcome distribution of the smoke observations
code, o, e = R.run(
    c, f"{P} -c \"import json,collections;"
       f"rows=[json.loads(l) for l in open('{OUT}/lane_m_smoke_v2/observations.jsonl')];"
       "print(collections.Counter(r['validation_status'] for r in rows));"
       "print(collections.Counter((r['subject_id'][:2], r['worker_result'].get('phase'))"
       " for r in rows if r['validation_status']!='pass'))\"", timeout=60)
c.close()
print("SMOKE_V2_DONE")
