import _remote

c = _remote.connect()
CMDS = [
    "ls /root/mk_v2_runs/e3_b9_calib/ | head -60",
    # queue + stage2 pending accounting
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob, os\n"
    "base = '/root/mk_v2_runs/e3_b9_calib'\n"
    "for f in sorted(os.listdir(base)):\n"
    "    p = os.path.join(base, f)\n"
    "    if f.endswith('.json') and os.path.isfile(p):\n"
    "        print(f, os.path.getsize(p))\n"
    "EOF\n",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o)
    print('=====')
c.close()
print('DONE')
