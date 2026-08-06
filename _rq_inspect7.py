import _remote

c = _remote.connect()
CMDS = [
    "sed -n '85,135p' /root/mk_v2/scripts/_mutant_worker.py",
    "sed -n '310,345p' /root/mk_v2/scripts/_mutant_worker.py",
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "m = json.load(open('/root/mk_v2_runs/e1/cse_run_manifest_lane3.json'))\n"
    "s = m.get('search', {})\n"
    "print('all_policies (%d):' % len(s.get('stress_policies') or []))\n"
    "print(s.get('stress_policies'))\n"
    "ps = m.get('policy_skip') or {}\n"
    "print('policy_skip kernels:', list(ps.keys()))\n"
    "for k, v in ps.items():\n"
    "    print(' ', k, '->', v)\n"
    "# also check the p96-specific manifest\n"
    "m2 = json.load(open('/root/mk_v2_runs/e1/cse_run_manifest_lane3_p96_5400.json'))\n"
    "print('p96 manifest search:', json.dumps(m2.get('search', {}), ensure_ascii=False)[:400])\n"
    "print('p96 manifest policy_skip:', m2.get('policy_skip'))\n"
    "print('p96 manifest timeout:', m2.get('timeout_s'), m2.get('worker_timeout_s'))\n"
    "print('p96 keys:', list(m2.keys()))\n"
    "EOF\n",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=90, echo=False)
    print(o)
    if e.strip():
        print('STDERR:', e[:500])
    print('====')
c.close()
print('RQ_INSPECT7_DONE')
