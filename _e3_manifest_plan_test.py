"""E3 ignition step 1: build the wave-1 subject manifest input + plan-build test.

1. Build subjects JSONL (653) for build_fse_subject_manifest.py:
   subject_id/dataset/task_id/language/candidate_path/reference_path/contract.
   reference_path = the KernelBench task module (source of Model + get_inputs).
2. Run build_fse_subject_manifest.py (hashes sources, no execution).
3. Plan-build TEST on a 3-subject subset x the v1 strategy matrix: does the
   signed contract authorize every matrix case? (in_contract scope hard-gates.)
"""
import _remote as R

mk_input = r"""
import json
from pathlib import Path

import glob
task_files = {}
for f in glob.glob('/root/mk_v2_runs/e3_b9_calib/calibration*.jsonl'):
    for line in open(f):
        if line.strip():
            r = json.loads(line)
            if r.get('task_key') and r.get('task_file'):
                task_files[r['task_key']] = r['task_file']
print('task_file map entries (from B9 ledgers):', len(task_files))

contracts = {}
for line in open('/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_signed_v1.jsonl',
                 encoding='utf-8'):
    r = json.loads(line)
    contracts[r['task_key']] = r['contract']
print('signed contracts:', len(contracts))

out = open('/root/mk_v2_runs/e3_campaign/wave1_manifest_input.jsonl', 'w')
n, miss_tf, miss_ct = 0, set(), set()
for line in open('/root/mk_v2_runs/e3_campaign/wave1_subjects.jsonl'):
    s = json.loads(line)
    tk = s['task_key']
    tf = task_files.get(tk) or task_files.get(tk.replace('KB_', '', 1))
    ct = contracts.get(tk)
    if tf is None:
        miss_tf.add(tk); continue
    if ct is None:
        miss_ct.add(tk); continue
    out.write(json.dumps({
        'subject_id': s['subject_id'],
        'dataset': s['corpus'],
        'task_id': tk,
        'language': 'cuda',
        'candidate_path': s['candidate_path'],
        'reference_path': '/root/mk_v2/' + tf,
        'contract': ct,
        'metadata': {'stable_id': s['stable_id'],
                     'scope_id': 'e3_campaign_scope_v1'},
    }) + '\n')
    n += 1
out.close()
print('manifest input rows:', n, 'missing task_file:', sorted(miss_tf)[:5],
      'missing contract:', sorted(miss_ct)[:5])
assert not miss_tf and not miss_ct and n == 653, (n, len(miss_tf), len(miss_ct))
print('INPUT_OK')
"""

plan_test = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, '/root/mk_v2')
from src.experiments.protocol import plan_from_files

# 3-subject subset manifest (rebuild through the official builder for hashes)
rows = [json.loads(l) for l in
        open('/root/mk_v2_runs/e3_campaign/wave1_manifest_input.jsonl')]
sub = rows[:2] + rows[-1:]   # 2x C3 + 1x C5
with open('/root/mk_v2_runs/e3_campaign/subset_input.jsonl', 'w') as fh:
    for r in sub:
        fh.write(json.dumps(r) + '\n')
print('subset:', [r['subject_id'] for r in sub])
"""

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_mk_input.py", "w") as fh:
    fh.write(mk_input)
with sftp.open("/root/mk_v2/_e3_plan_test_prep.py", "w") as fh:
    fh.write(plan_test)
# also push the local strategy matrix (missing on remote)
sftp.put("configs/fse_strategy_matrix.json",
         "/root/mk_v2/configs/fse_strategy_matrix.json")
sftp.close()

P = "/root/miniconda3/bin/python"
code, o, e = R.run(c, f"cd /root/mk_v2 && {P} -u _e3_mk_input.py", timeout=300)
if code != 0:
    raise SystemExit("manifest input failed")
R.run(c, f"cd /root/mk_v2 && {P} -u _e3_plan_test_prep.py", timeout=120)
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/build_fse_subject_manifest.py "
       "--root / "
       "--input /root/mk_v2_runs/e3_campaign/subset_input.jsonl "
       "--output /root/mk_v2_runs/e3_campaign/subset_manifest.json",
    timeout=300)
if code != 0:
    raise SystemExit("subset manifest build failed")
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/plan_fse_experiment.py "
       "--subjects /root/mk_v2_runs/e3_campaign/subset_manifest.json "
       "--strategy-matrix configs/fse_strategy_matrix.json "
       "--output /root/mk_v2_runs/e3_campaign/subset_plan.json 2>&1 | tail -15",
    timeout=600)
print("PLAN_TEST_EXIT", code)
c.close()
print("STEP1_DONE")
