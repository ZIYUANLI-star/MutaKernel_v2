import _remote

c = _remote.connect()
CMDS = [
    "free -g; echo ---; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader",
    # stage2 unit sizes
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "base = '/root/mk_v2_runs/e3_b9_calib'\n"
    "q = json.load(open(base + '/queue_state.json'))\n"
    "s2 = q.get('stage2_deferred') or []\n"
    "print('s2 entry type:', type(s2[0]).__name__)\n"
    "units = q.get('units', [])\n"
    "by_name = {}\n"
    "for u in units:\n"
    "    if isinstance(u, dict):\n"
    "        by_name[u.get('unit')] = u\n"
    "rows = []\n"
    "for it in s2:\n"
    "    u = it if isinstance(it, dict) else by_name.get(it, {'unit': it})\n"
    "    rows.append(u)\n"
    "rows.sort(key=lambda u: -(u.get('reserve_gb') or 0))\n"
    "tot = 0\n"
    "for u in rows:\n"
    "    print('%-26s reserve=%sGB peak=%sGB wall_slow=%ss timeout=%ss' % (\n"
    "        u.get('unit'), u.get('reserve_gb'), u.get('est_peak_gb'),\n"
    "        u.get('est_wall_s_slow'), u.get('unit_timeout_s')))\n"
    "    tot += (u.get('est_wall_s_slow') or 0)\n"
    "print('TOTAL est slow: %.1fh' % (tot/3600.0))\n"
    "EOF\n",
    # how was the driver started for the fp16fix wave? check guard + driver usage
    "tail -30 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.sh; echo ---; "
    "grep -n 'lane\\|LANE\\|reserve' /root/mk_v2/_b9_calib_driver_v2.py | head -25",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=90, echo=False)
    print(o)
    if e.strip():
        print('STDERR:', e[:400])
    print('=====')
c.close()
print('DONE')
