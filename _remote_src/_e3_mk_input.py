
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
