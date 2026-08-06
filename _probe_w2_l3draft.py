import _remote as R

py = r"""
import json
from collections import Counter

print('===== L3 draft contracts =====')
lv = Counter(); n = 0
with open('/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft_l3.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        n += 1
        lv[str(r.get('task_key', '')).split('_P')[0]] += 1
print('total', n, 'levels', dict(lv))
print(open('/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft_l3.freeze.json').read())

print()
print('===== C5 L3 frame row: origin field =====')
seen = 0
with open('/root/mk_v2_runs/e2_reconcile/C5_collection_frame.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        if 'L3' in str(r.get('task_key', '')) and r.get('included'):
            print(json.dumps(r, ensure_ascii=False)[:600])
            seen += 1
            if seen >= 2:
                break

print()
print('===== _c5_stage.py head =====')
src = open('/root/mk_v2/_c5_stage.py').read()
print(src[:2500])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_w2d.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_w2d.py",
      timeout=300)
c.close()
print("PROBE_DONE")
