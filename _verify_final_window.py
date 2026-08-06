# -*- coding: utf-8 -*-
"""清算窗审阅材料核验(只读):三项待签认修正的建议目标判级与 #7 重判证据链。"""
import _remote

SCRIPT = r'''
import json, glob, os, collections

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

print('=== final_window_summary.json ===')
s = json.load(open('/root/mk_v2_runs/e1/final_window_summary.json'))
print(json.dumps(s, ensure_ascii=False, indent=1)[:4500])

print()
print('=== final_window_review/ 目录 ===')
for f in sorted(glob.glob('/root/mk_v2_runs/e1/final_window_review/*')):
    print(' ', os.path.basename(f), os.path.getsize(f))
'''

c = _remote.connect()
_remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300)
c.close()
