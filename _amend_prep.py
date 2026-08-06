import _remote

c = _remote.connect()
CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "rep = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "print('generated_at:', rep.get('generated_at'))\n"
    "print('top keys:', list(rep.keys()))\n"
    "for k in rep:\n"
    "    v = rep[k]\n"
    "    if isinstance(v, dict):\n"
    "        print(k, '->', json.dumps(v, ensure_ascii=False)[:500])\n"
    "    elif isinstance(v, list):\n"
    "        print(k, '-> list of', len(v))\n"
    "verd = rep.get('witness_verdicts') or rep.get('verdicts') or []\n"
    "if isinstance(verd, list) and verd:\n"
    "    from collections import Counter\n"
    "    print('verdict counts:', dict(Counter(v.get('verdict') for v in verd)))\n"
    "    for v in verd:\n"
    "        if v.get('verdict') not in ('CONFIRMED',):\n"
    "            print(' ', v.get('probe_id'), v.get('stage'), v.get('verdict'), str(v.get('note',''))[:80])\n"
    "EOF\n"
)
_, o, e = _remote.run(c, CMD, timeout=90, echo=False)
print(o)
if e.strip():
    print('STDERR:', e[:500])
c.close()
print('DONE')
