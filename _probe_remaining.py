import _remote

SCRIPT = r"""
import json, glob

p = json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))
lanes = {str(l['lane']): l for l in p['lanes']}
for i in ('3', '4', '5'):
    l = lanes[i]
    print(f"lane{i}: probe_count={l.get('probe_count')} est_hours={l.get('est_hours')} kernels={l.get('kernel_count')}")

def probes_of(l):
    for key in ('probes', 'probe_ids', 'targets'):
        if key in l:
            return l[key]
    return None

sample = lanes['4']
print('lane4 keys:', list(sample.keys()))

for i in ('3', '4', '5'):
    l = lanes[i]
    pl = probes_of(l)
    comp = json.load(open(f'/root/mk_v2_runs/e1/cse_completed_lane{i}.json'))
    comp_ids = set(comp if isinstance(comp, list) else comp.keys())
    if pl is not None:
        rem = [x for x in pl if x not in comp_ids]
        print(f'lane{i}: planned={len(pl)} completed_ledger={len(comp_ids)} remaining={len(rem)}')
        print('  next few remaining:', rem[:6])
    else:
        print(f'lane{i}: no probe list key; completed_ledger={len(comp_ids)}')
print('DONE_REMAIN')
"""

GREP = r"""
grep -rn "def grade_cse_evidence" /root/mk_v2 --include=*.py | head -3
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:2000])
code, o, e = _remote.run(c, GREP, timeout=60, echo=False)
print("== grade fn location ==")
print(o)
c.close()
