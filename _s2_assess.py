"""Assess B9 stage-2 readiness: queue, memory profiles, stage-1 outcome."""
import _remote

c = _remote.connect()
CMDS = [
    # stage/queue markers and layout
    "ls /root/mk_v2_runs/b9_calib_v2/ 2>/dev/null | head -30; echo ---; "
    "ls /root/mk_v2_runs/b9_calib_v2/*.json 2>/dev/null | head -20",
    # queue state: stage2 units
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob, os\n"
    "base = '/root/mk_v2_runs/b9_calib_v2'\n"
    "for f in sorted(glob.glob(base + '/queue*.json')) + sorted(glob.glob(base + '/*stage2*')):\n"
    "    print('FILE:', f, os.path.getsize(f))\n"
    "q = None\n"
    "for cand in (base + '/queue_v2.json', base + '/queue.json'):\n"
    "    if os.path.exists(cand):\n"
    "        q = json.load(open(cand)); print('loaded', cand); break\n"
    "if q is not None:\n"
    "    items = q if isinstance(q, list) else q.get('units') or q.get('queue') or []\n"
    "    print('total units:', len(items))\n"
    "    if items and isinstance(items[0], dict):\n"
    "        print('keys:', list(items[0].keys()))\n"
    "        from collections import Counter\n"
    "        st = Counter(str(i.get('stage', i.get('wave',''))) for i in items)\n"
    "        print('stage distribution:', dict(st))\n"
    "EOF\n",
    # completed rows vs pending; memory profile summary
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob, os\n"
    "base = '/root/mk_v2_runs/b9_calib_v2'\n"
    "res = glob.glob(base + '/results/*.json')\n"
    "print('result files:', len(res))\n"
    "for f in sorted(glob.glob(base + '/*.md')) + sorted(glob.glob(base + '/*profile*')) + sorted(glob.glob(base + '/*mem*')):\n"
    "    print('AUX:', f)\n"
    "for name in ('STAGE1_DONE','STAGE2_DONE','completed.json'):\n"
    "    p = os.path.join(base, name)\n"
    "    if os.path.exists(p):\n"
    "        print(name, 'exists, size', os.path.getsize(p))\n"
    "EOF\n",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=90, echo=False)
    print(o)
    if e.strip():
        print('STDERR:', e[:300])
    print('=====')
c.close()
print('S2_ASSESS_DONE')
