import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "with open('/root/mk_v2_runs/e3_b9_calib/calibration_v2_lane0.jsonl') as f:\n"
         "    recs = [json.loads(l) for l in f if l.strip()]\n"
         "print('lane0 v2 records:', len(recs))\n"
         "ok = [r for r in recs if r.get('control_status') in ('calibrated_ok','ok') or 'tol' in str(r)]\n"
         "r = recs[-1]\n"
         "print(json.dumps(r, default=str)[:1500])\n"
         "EOF", timeout=60)
c.close()
print("DONE")
