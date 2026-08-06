import _remote

c = _remote.connect()
CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, os\n"
    "p = '/root/mk_v2_runs/e1/requeue_final/observations.jsonl'\n"
    "if os.path.exists(p):\n"
    "    for line in open(p):\n"
    "        r = json.loads(line)\n"
    "        ev = r.get('evidence') or {}\n"
    "        print('%-28s %-26s valid=%s random=%s stress=%s div=%s wall=%.0fs' % (\n"
    "            r['probe_id'], r['outcome'], r.get('valid_rounds'),\n"
    "            ev.get('random_rounds_passed'), ev.get('stress_rounds_passed'),\n"
    "            bool(r.get('divergence')), (r.get('wall_ms') or 0)/1000.0))\n"
    "else:\n"
    "    print('no obs yet')\n"
    "EOF\n"
)
_, o, e = _remote.run(c, CMD, timeout=60, echo=False)
print(o)
c.close()
print('DONE')
