import _remote

c = _remote.connect()
code, o, e = _remote.run(c, """/root/miniconda3/bin/python - <<'EOF'
import json
rec = json.loads(open('/root/mk_v2_runs/e1/cse_observations_lane4.jsonl').readline())
def show(d, prefix=''):
    for k, v in d.items():
        if isinstance(v, dict) and len(str(v)) > 200:
            print(prefix + k, ': dict keys=', list(v.keys()))
            show(v, prefix + '  ')
        else:
            s = str(v)
            print(prefix + k, ':', s[:180])
show(rec)
print('---FALSIFIED sample---')
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane4.jsonl'):
    r = json.loads(ln)
    if r.get('outcome') == 'FALSIFIED':
        print(json.dumps(r)[:3000])
        break
EOF""", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1500])
c.close()
