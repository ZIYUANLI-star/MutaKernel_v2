import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "recs = []\n"
         "for lane in ('calibration_lane0.jsonl', 'calibration_lane1.jsonl'):\n"
         "    with open('/root/mk_v2_runs/e3_b9_calib/' + lane) as f:\n"
         "        for l in f:\n"
         "            if l.strip():\n"
         "                recs.append(json.loads(l))\n"
         "print('records:', len(recs))\n"
         "r = recs[-1]\n"
         "print('keys:', sorted(r.keys()))\n"
         "print(json.dumps({k: r[k] for k in list(sorted(r.keys()))[:16]}, default=str)[:900])\n"
         "EOF", timeout=120)
c.close()
print("DONE")
