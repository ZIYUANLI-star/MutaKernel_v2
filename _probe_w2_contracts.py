import _remote as R

py = r"""
import json
from collections import Counter

print('===== signed_v1 contracts coverage =====')
lv = Counter(); n = 0
sample = None
with open('/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_signed_v1.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        n += 1
        tk = str(r.get('task_key') or '')
        lv[tk.split('_P')[0]] += 1
        if sample is None and 'L3' in tk:
            sample = r
print('total', n, 'levels', dict(lv))
print('signed L3 sample keys:', sorted(sample.keys()) if sample else None)
if sample:
    print('review fields:', json.dumps({k: v for k, v in sample.items()
        if 'review' in k or 'sign' in k or 'status' in k}, ensure_ascii=False)[:800])
    print('task_key:', sample['task_key'])

print()
print('===== freeze record =====')
print(open('/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_signed_v1.freeze.json').read())

print()
print('===== C5 collection frame: has code? which waves =====')
n = 0; has_code = 0; keys = None
tasks = Counter()
with open('/root/mk_v2_runs/e2_reconcile/C5_collection_frame.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        n += 1
        if keys is None:
            keys = sorted(r.keys())
        if r.get('code') or r.get('candidate_source') or r.get('kernel_code'):
            has_code += 1
        tasks[str(r.get('task_key', '')).split('_P')[0]] += 1
print('C5 frame rows', n, 'with inline code', has_code)
print('keys:', keys)
print('task levels:', dict(tasks))

print()
print('===== C3 frame L3 rows =====')
n3 = 0
with open('/root/mk_v2_runs/e2_reconcile/C3_collection_frame.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        if 'L3' in str(r.get('task_key', '')):
            n3 += 1
print('C3 frame L3 rows:', n3)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_w2c.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_w2c.py",
      timeout=300)
c.close()
print("PROBE_DONE")
