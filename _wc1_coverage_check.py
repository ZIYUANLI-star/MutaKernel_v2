"""Check WC-1 report coverage: which witnesses were independently replayed."""
import _remote as R

c = R.connect()
cmds = [
    "find /root/mk_v2_runs/e1 -maxdepth 2 -name 'wc1*' -o -maxdepth 2 -name '*wc_*' | head",
    "/root/miniconda3/bin/python -c \"import json;"
    "d=json.load(open('/root/mk_v2_runs/e1/wc1_report.json'));"
    "print('keys:', list(d.keys()));"
    "v=d.get('verdicts') or d.get('results') or {};"
    "print('verdict rows:', len(v));"
    "import collections;"
    "c=collections.Counter((r.get('verdict') if isinstance(r,dict) else str(r)) for r in (v.values() if isinstance(v,dict) else v));"
    "print(dict(c))\" 2>&1",
    "/root/miniconda3/bin/python -c \"import json;"
    "d=json.load(open('/root/mk_v2_runs/e1/wc1_report.json'));"
    "print(json.dumps(d, ensure_ascii=False)[:900])\" 2>&1",
]
for cmd in cmds:
    print("### " + cmd[:70])
    R.run(c, cmd, timeout=120)
c.close()
print("WC1_CHECK_DONE")
