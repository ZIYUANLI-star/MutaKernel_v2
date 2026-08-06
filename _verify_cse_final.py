# -*- coding: utf-8 -*-
"""CSE 收官终版核验(只读):主账+tagged 守恒、终版分布、三项待签认修正的建议目标判级。"""
import _remote

SCRIPT = r'''
import json, collections, glob, os, hashlib

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

print('=== e1 目录下 final/tagged 相关文件 ===')
for f in sorted(glob.glob('/root/mk_v2_runs/e1/*final*') + glob.glob('/root/mk_v2_runs/e1/*tagged*') + glob.glob('/root/mk_v2_runs/e1/FINAL*') + glob.glob('/root/mk_v2_runs/e1/*FINAL*')):
    print(' ', f, os.path.getsize(f) if os.path.isfile(f) else '<dir>')

print()
print('=== equiv 零变动 ===')
h = hashlib.md5(open('/root/mk_v2_runs/e1/equiv_observations.jsonl','rb').read()).hexdigest()
print('equiv md5:', h, '(上次 ab3c36752fc8d68ec5c5c45a8c8ab7dc)')
summ = json.load(open('/root/mk_v2_runs/e1/equiv_summary.json'))
print('equiv grades:', summ['grades'])

print()
print('=== CSE 主账(lane0-5)===')
main = {}
for p in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane*.jsonl')):
    if '.bak' in p or 'timeout' in p or 'env_v1' in p or 'tagged' in p:
        continue
    for o in load(p):
        main[o['probe_id']] = o
print('主账 unique:', len(main))
print('主账分布:', dict(collections.Counter(o.get('validation_status') for o in main.values())))
'''

c = _remote.connect()
_remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300)
c.close()
