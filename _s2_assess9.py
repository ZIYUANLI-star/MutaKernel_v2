import _remote

c = _remote.connect()
CMDS = [
    "grep -n 'unit_timeout_s\\|timeout' /root/mk_v2/_b9_calib_driver_v2.py | head -15",
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "base = '/root/mk_v2_runs/e3_b9_calib'\n"
    "q = json.load(open(base + '/queue_state.json'))\n"
    "units = q['units']\n"
    "print('units container:', type(units).__name__, 'n=', len(units))\n"
    "s2 = q['stage2_deferred']\n"
    "names = [u['unit'] for u in s2]\n"
    "in_units = sum(1 for n in names if n in units)\n"
    "print('stage2 in units dict: %d/%d' % (in_units, len(names)))\n"
    "if in_units:\n"
    "    n0 = next(n for n in names if n in units)\n"
    "    print('example entry:', json.dumps(units[n0], default=str)[:300])\n"
    "print('pending type:', type(q['pending']).__name__)\n"
    "print('done sample:', q['done'][:3] if isinstance(q['done'], list) else 'dict')\n"
    "EOF\n",
    "sed -n '160,230p' /root/mk_v2/_b9_calib_driver_v2.py",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o)
    if e.strip():
        print('STDERR:', e[:400])
    print('=====')
c.close()
print('DONE')
