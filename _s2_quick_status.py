"""Quick B9 stage-2 status: queue counts, drivers, latest run_error count."""
import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'PY'\n"
         "import glob, json\n"
         "from collections import Counter\n"
         "q = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
         "print('pending', len(q['pending']), 'claimed', len(q['claimed']),\n"
         "      'done', len(q['done']))\n"
         "rows = {}\n"
         "for f in sorted(glob.glob('/root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl')):\n"
         "    for line in open(f):\n"
         "        if line.strip():\n"
         "            r = json.loads(line)\n"
         "            rows[r['unit']] = r\n"
         "print('latest statuses:', dict(Counter(r['control_status'] for r in rows.values())))\n"
         "PY", timeout=180)
R.run(c, "pgrep -fc '[b]9_calib_driver' || echo 0; "
         "pgrep -fc '[g]uard_b9' || echo 0", timeout=60)
R.run(c, "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader",
      timeout=60)
c.close()
print("S2_STATUS_DONE")
