import _remote

c = _remote.connect()
CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "base = '/root/mk_v2_runs/e3_b9_calib'\n"
    "q = json.load(open(base + '/queue_state.json'))\n"
    "print('wave:', q.get('wave'))\n"
    "print('scope_decision:', str(q.get('scope_decision'))[:300])\n"
    "print('pending:', len(q.get('pending') or []))\n"
    "print('claimed:', len(q.get('claimed') or []))\n"
    "print('done:', len(q.get('done') or []))\n"
    "s2 = q.get('stage2_deferred') or []\n"
    "print('stage2_deferred:', len(s2))\n"
    "units = {u['unit']: u for u in q.get('units', [])}\n"
    "import math\n"
    "tot_est = 0\n"
    "for name in s2[:50]:\n"
    "    u = units.get(name if isinstance(name, str) else name.get('unit'), {})\n"
    "    if isinstance(name, dict):\n"
    "        u = name\n"
    "    est = u.get('est_peak_gb'); wall = u.get('est_wall_s_slow'); to = u.get('unit_timeout_s')\n"
    "    tot_est += (wall or 0)\n"
    "    print('  %-24s peak=%.0fGB wall_slow=%ss timeout=%ss' % (u.get('unit', name), est or -1, wall, to))\n"
    "print('sum est_wall_s_slow: %.0fs = %.1fh' % (tot_est, tot_est/3600.0))\n"
    "print()\n"
    "# leftover pending that is not stage2?\n"
    "pend = q.get('pending') or []\n"
    "print('pending list sample:', pend[:10])\n"
    "EOF\n"
)
_, o, e = _remote.run(c, CMD, timeout=90, echo=False)
print(o)
if e.strip():
    print('STDERR:', e[:800])
c.close()
print('DONE')
