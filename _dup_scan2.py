"""Check how _b9_aggregate handles v1 vs v2 rows for the 13 overlapping units."""
import _remote

CMD = (
    "grep -n 'calibration\\|v2\\|dedup\\|prefer\\|carried\\|lane' /root/mk_v2/_b9_aggregate.py | head -30; "
    "echo SEP; head -40 /root/mk_v2/_b9_aggregate.py; echo SEP; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob\n"
    "# what status do the 13 overlapping units have in v1 rows vs v2 rows\n"
    "v1 = {}\n"
    "for f in sorted(glob.glob('/root/mk_v2_runs/e3_b9_calib/calibration_lane*.jsonl')):\n"
    "    for line in open(f):\n"
    "        if line.strip():\n"
    "            r = json.loads(line)\n"
    "            v1[r.get('unit')] = (f.split('/')[-1], r.get('control_status'), r.get('wave'))\n"
    "v2 = {}\n"
    "for f in sorted(glob.glob('/root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl')):\n"
    "    for line in open(f):\n"
    "        if line.strip():\n"
    "            r = json.loads(line)\n"
    "            v2[r.get('unit')] = (f.split('/')[-1], r.get('control_status'), r.get('wave'))\n"
    "both = sorted(set(v1) & set(v2))\n"
    "print('units in both:', len(both))\n"
    "for u in both:\n"
    "    print(' ', u, '| v1:', v1[u][1], '| v2:', v2[u][1])\n"
    "only_v1 = sorted(set(v1) - set(v2))\n"
    "print('v1-only units (carried, no v2 row):', len(only_v1))\n"
    "for u in only_v1:\n"
    "    print(' ', u, v1[u][1])\n"
    "EOF\n"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=180, echo=False)
c.close()
print(o)
print("DUP_SCAN2_DONE")
