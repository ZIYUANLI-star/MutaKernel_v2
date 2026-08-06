# -*- coding: utf-8 -*-
"""签认前备账(只读):FALSIFIED 14 明细、逐类分布、待签认探针证据、审阅文件。"""
import _remote

SCRIPT = r'''
import json, collections, glob, os

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

# 类别映射:与 baseline 观测 join
b = load('/root/mk_v2_runs/e1/baseline_observations.jsonl')
cat = {o['probe_id']: o['operator_category'] for o in b}

main = {}
for p in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane*.jsonl')):
    if '.bak' in p or 'timeout' in p or 'env_v1' in p:
        continue
    for o in load(p):
        main[o['probe_id']] = o

print('=== CSE 终版(现账,签认前)===')
dist = collections.Counter(o['validation_status'] for o in main.values())
print('总分布:', dict(dist), '| unique:', len(main))
for st in ('pass','fail','inconclusive'):
    d = collections.Counter(cat[pid] for pid,o in main.items() if o['validation_status']==st)
    print('  %s by category:' % st, dict(sorted(d.items())))
print()
print('FALSIFIED 14 明细:')
for pid, o in sorted(main.items()):
    if o['validation_status']=='fail':
        print('  %-38s cat=%s op=%-22s valid_rounds=%s' % (pid, cat[pid], o.get('operator_name'), o.get('valid_rounds')))

print()
print('=== 待签认 6+1 条的账面证据 ===')
p46 = main.get('L1_P46__index_replace__5')
print('L1_P46__index_replace__5: status=%s valid_rounds=%s divergence=%s' % (
    p46['validation_status'], p46.get('valid_rounds'), str(p46.get('divergence'))[:200]))
tr = p46.get('trials')
if tr:
    print('  trials 条数:', len(tr) if isinstance(tr, list) else type(tr))

p37s = [pid for pid in main if pid.startswith('L1_P37')]
print('P37 相关探针(主账):')
for pid in sorted(p37s):
    o = main[pid]
    print('  %-38s cat=%s status=%s valid_rounds=%s' % (pid, cat[pid], o['validation_status'], o.get('valid_rounds')))

print()
print('=== equiv 侧逐类(收官,零变动已核)===')
e = load('/root/mk_v2_runs/e1/equiv_observations.jsonl')
for g in ('WITNESSED_NON_EQUIVALENT','LIKELY_EQUIVALENT','INCONCLUSIVE'):
    d = collections.Counter(cat[o['probe_id']] for o in e if o['evidence_grade']==g)
    print('  %s: total=%d by cat=%s' % (g, sum(d.values()), dict(sorted(d.items()))))
inc = [o for o in e if o['evidence_grade']=='INCONCLUSIVE']
for o in inc:
    print('  equiv INC probe:', o['probe_id'], '| cat', cat[o['probe_id']], '|', str(o.get('reason'))[:120])

print()
print('=== baseline 执行级 INCONCLUSIVE 类逐类(Table 10 口径备查)===')
for st in ('unknown','inconclusive_timeout','inconclusive_worker_failure','excluded_control_failed'):
    d = collections.Counter(o['operator_category'] for o in b if o['status']==st)
    print('  %s: total=%d by cat=%s' % (st, sum(d.values()), dict(sorted(d.items()))))

print()
print('=== final_window_review 文件内容 ===')
for f in sorted(glob.glob('/root/mk_v2_runs/e1/final_window_review/*')):
    if os.path.isdir(f):
        for g in sorted(glob.glob(f + '/*')):
            print('--', g, os.path.getsize(g))
    else:
        print('--', f)
        print(open(f).read()[:800])
'''

c = _remote.connect()
_remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300)
c.close()
