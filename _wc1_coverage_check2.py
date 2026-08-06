"""Inspect wc1_report.json in witness_confirmation dir."""
import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'PY'\n"
         "import json, collections\n"
         "d = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
         "print('keys:', list(d.keys()))\n"
         "for k, v in d.items():\n"
         "    if isinstance(v, list):\n"
         "        print(k, 'list len', len(v))\n"
         "        if v and isinstance(v[0], dict):\n"
         "            print('  item keys:', sorted(v[0].keys()))\n"
         "            c2 = collections.Counter(str(r.get('verdict')) for r in v)\n"
         "            print('  verdicts:', dict(c2))\n"
         "    elif isinstance(v, dict):\n"
         "        print(k, 'dict keys', list(v.keys())[:10])\n"
         "    else:\n"
         "        print(k, '=', str(v)[:120])\n"
         "PY", timeout=120)
c.close()
print("DONE")
