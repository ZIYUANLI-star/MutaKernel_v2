import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "q = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
         "units = q['units']\n"
         "k = next(iter(units))\n"
         "print('unit key sample:', k)\n"
         "print('unit value:', json.dumps(units[k])[:500])\n"
         "print('pending:', len(q['pending']), 'done:', len(q['done']))\n"
         "EOF", timeout=60)
# the actual per-unit execution block
R.run(c, "sed -n '120,240p' /root/mk_v2/_b9_calib_driver_v2.py", timeout=60)
c.close()
print("DONE")
