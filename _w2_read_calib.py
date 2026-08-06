import _remote as R

c = R.connect()
R.run(c, "grep -n 'add_argument\\|def main\\|queue_state\\|unit_size_table' "
         "/root/mk_v2/_b9_calib_driver_v2.py | head -40", timeout=60)
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "q = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
         "print('queue keys:', list(q.keys()))\n"
         "units = q.get('units') or q.get('queue') or []\n"
         "print('units:', len(units) if isinstance(units, list) else type(units))\n"
         "if isinstance(units, list) and units:\n"
         "    print('first:', json.dumps(units[0])[:400])\n"
         "    done = [u for u in units if (u.get('status') or '') == 'done']\n"
         "    print('done:', len(done))\n"
         "import os\n"
         "print(sorted(os.listdir('/root/mk_v2_runs/e3_b9_calib'))[:30])\n"
         "EOF", timeout=60)
c.close()
print("DONE")
