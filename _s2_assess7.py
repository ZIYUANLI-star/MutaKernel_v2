import _remote

c = _remote.connect()
CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "base = '/root/mk_v2_runs/e3_b9_calib'\n"
    "q = json.load(open(base + '/queue_state.json'))\n"
    "units = {u['unit']: u for u in q.get('units', []) if isinstance(u, dict)}\n"
    "rows = []\n"
    "for lane in (0, 1):\n"
    "    for line in open(base + '/calibration_v2_lane%d.jsonl' % lane):\n"
    "        r = json.loads(line)\n"
    "        rows.append(r)\n"
    "print('calib rows:', len(rows), 'sample keys:', list(rows[0].keys())[:20])\n"
    "import statistics\n"
    "ratios_slow, ratios_fast = [], []\n"
    "tot_actual = 0\n"
    "for r in rows:\n"
    "    uid = r.get('unit') or r.get('unit_id')\n"
    "    u = units.get(uid)\n"
    "    wall = r.get('wall_s') or (r.get('wall_ms') or 0)/1000.0\n"
    "    tot_actual += wall or 0\n"
    "    if u and wall:\n"
    "        if u.get('est_wall_s_slow'):\n"
    "            ratios_slow.append(wall / u['est_wall_s_slow'])\n"
    "        if u.get('est_wall_s_fast'):\n"
    "            ratios_fast.append(wall / u['est_wall_s_fast'])\n"
    "print('stage-1 actual total: %.1fh over %d rows' % (tot_actual/3600.0, len(rows)))\n"
    "if ratios_slow:\n"
    "    print('actual/slow_est: median %.2f p90 %.2f max %.2f (n=%d)' % (\n"
    "        statistics.median(ratios_slow), sorted(ratios_slow)[int(0.9*len(ratios_slow))], max(ratios_slow), len(ratios_slow)))\n"
    "if ratios_fast:\n"
    "    print('actual/fast_est: median %.2f p90 %.2f max %.2f' % (\n"
    "        statistics.median(ratios_fast), sorted(ratios_fast)[int(0.9*len(ratios_fast))], max(ratios_fast)))\n"
    "# stage-2 projections\n"
    "s2 = q.get('stage2_deferred') or []\n"
    "fast = sum((u.get('est_wall_s_fast') or 0) for u in s2)\n"
    "slow = sum((u.get('est_wall_s_slow') or 0) for u in s2)\n"
    "print('stage2 est fast %.1fh slow %.1fh' % (fast/3600.0, slow/3600.0))\n"
    "med = statistics.median(ratios_slow) if ratios_slow else None\n"
    "if med:\n"
    "    print('stage2 projected from slow*median-ratio: %.1fh' % (slow*med/3600.0))\n"
    "medf = statistics.median(ratios_fast) if ratios_fast else None\n"
    "if medf:\n"
    "    print('stage2 projected from fast*median-ratio: %.1fh' % (fast*medf/3600.0))\n"
    "EOF\n"
)
_, o, e = _remote.run(c, CMD, timeout=120, echo=False)
print(o)
if e.strip():
    print('STDERR:', e[:800])
c.close()
print('DONE')
