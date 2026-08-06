"""Inspect the promoted stage-2 unit records vs stage-1 schema."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "u=q['units']\n"
    "print('--- promoted unit L1_P23__float32:')\n"
    "print(json.dumps(u.get('L1_P23__float32'), indent=1, default=str)[:800])\n"
    "done_key=[k for k in u if k not in q['pending'] and k not in q['claimed']][0]\n"
    "print('--- stage-1 done unit', done_key, ':')\n"
    "print(json.dumps(u[done_key], indent=1, default=str)[:800])\n"
    "import collections\n"
    "missing=collections.Counter()\n"
    "ref=set(u[done_key].keys())\n"
    "for k in list(q['pending'])+list(q['claimed']):\n"
    "    missing.update(ref-set(u[k].keys()))\n"
    "print('--- fields missing across 44 promoted units:', dict(missing))\n"
    "EOF\n"
    "echo ===BAK===; /root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json.bak_s2_20260801T115741'))\n"
    "sd=q['stage2_deferred']\n"
    "print('deferred count:', len(sd), 'elem type:', type(sd[0]).__name__)\n"
    "print(json.dumps(sd[0], indent=1, default=str)[:800])\n"
    "print('in units dict already?', (sd[0] if isinstance(sd[0],str) else sd[0].get('unit')) in q['units'])\n"
    "EOF"),
    timeout=60, echo=False)
print(o)
c.close()
