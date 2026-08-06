import _remote

c = _remote.connect()
CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "base = '/root/mk_v2_runs/e3_b9_calib'\n"
    "q = json.load(open(base + '/queue_state.json'))\n"
    "print('queue_state type:', type(q).__name__)\n"
    "if isinstance(q, dict):\n"
    "    print('keys:', list(q.keys())[:10])\n"
    "    units = q.get('units') or q.get('queue') or []\n"
    "else:\n"
    "    units = q\n"
    "print('n units:', len(units))\n"
    "if units:\n"
    "    u0 = units[0] if isinstance(units, list) else list(units.values())[0]\n"
    "    print('unit keys:', list(u0.keys()) if isinstance(u0, dict) else type(u0))\n"
    "from collections import Counter\n"
    "vals = units if isinstance(units, list) else list(units.values())\n"
    "if vals and isinstance(vals[0], dict):\n"
    "    print('status:', dict(Counter(str(v.get('status')) for v in vals)))\n"
    "    print('stage:', dict(Counter(str(v.get('stage', v.get('wave'))) for v in vals)))\n"
    "    pend = [v for v in vals if str(v.get('status')) not in ('done','completed','ok')]\n"
    "    print('pending-ish:', len(pend))\n"
    "    for v in pend[:8]:\n"
    "        print(' ', json.dumps(v, default=str)[:220])\n"
    "# completed v2 counts + calibration rows\n"
    "for lane in (0, 1):\n"
    "    comp = json.load(open(base + '/completed_v2_lane%d.json' % lane))\n"
    "    n = 0\n"
    "    for line in open(base + '/calibration_v2_lane%d.jsonl' % lane):\n"
    "        n += 1\n"
    "    print('lane%d completed=%d calib_rows=%d' % (lane, len(comp), n))\n"
    "EOF\n"
)
_, o, e = _remote.run(c, CMD, timeout=90, echo=False)
print(o)
if e.strip():
    print('STDERR:', e[:800])
c.close()
print('DONE')
