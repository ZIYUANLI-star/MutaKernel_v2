import _remote as R

py = r"""
import json, os

def head_args(p, n=4000):
    src = open(p, encoding='utf-8', errors='replace').read()
    print('---', os.path.basename(p), '---')
    print(src[:n//4])
    print('  ...argparse...')
    for line in src.splitlines():
        ls = line.strip()
        if 'add_argument' in ls and len(ls) < 160:
            print('   ', ls)
    print()

for p in ('/root/mk_v2/scripts/build_fse_subject_manifest.py',
          '/root/mk_v2/scripts/prepare_external_datasets.py',
          '/root/mk_v2/scripts/reconcile_corpora.py',
          '/root/mk_v2/scripts/extract_contracts.py'):
    head_args(p)

print('===== draft contracts: how many, which tasks =====')
from collections import Counter
n = 0; lv = Counter(); status = Counter()
with open('/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        n += 1
        tk = r.get('task_key') or r.get('task_id') or ''
        if '_L' in str(tk):
            lv[str(tk).split('_P')[0]] += 1
        status[r.get('status') or r.get('review_status') or '?'] += 1
        if n == 1:
            print('first record keys:', sorted(r.keys()))
print('total', n, 'levels', dict(lv), 'status', dict(status))

print()
print('===== b9 calib driver v2: how units are enumerated =====')
src = open('/root/mk_v2/_b9_calib_driver_v2.py').read()
print(src[:2500])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_w2b.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_w2b.py",
      timeout=300)
c.close()
print("PROBE_DONE")
