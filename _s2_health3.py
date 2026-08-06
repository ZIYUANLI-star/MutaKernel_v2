"""Verify output pattern via a finished unit + sample calibration data quality."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "echo ===DONE_UNIT_LOG===; "
    "wc -c /root/mk_v2_runs/e3_b9_calib/units/L2_P9__float16/run.log; "
    "head -3 /root/mk_v2_runs/e3_b9_calib/units/L2_P9__float16/run.log; "
    "echo ===DONE_SUMMARY===; "
    "cat /root/mk_v2_runs/e3_b9_calib/units/L2_P9__float16/b9_L2_P9_summary.json; "
    "echo; echo ===CALIB_ROWS===; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob\n"
    "rows={}\n"
    "for f in sorted(glob.glob('/root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl')):\n"
    "    for line in open(f):\n"
    "        if line.strip():\n"
    "            r=json.loads(line); rows[r['unit']]=r\n"
    "from collections import Counter\n"
    "st=Counter(r.get('control_status') for r in rows.values())\n"
    "print('calibration rows:', len(rows), 'status:', dict(st))\n"
    "fp16=[r for r in rows.values() if r['unit'].endswith('float16')]\n"
    "fp32=[r for r in rows.values() if r['unit'].endswith('float32')]\n"
    "print('fp16 units:', len(fp16), 'fp32 units:', len(fp32))\n"
    "sam=[r for r in rows.values() if r.get('calibrated_tol')][:2]\n"
    "for r in sam:\n"
    "    print(json.dumps({k:r[k] for k in ('unit','control_status','calibrated_tol','p95_rel_err','wall_s') if k in r}))\n"
    "EOF\n"
    "echo ===STRACE_QUICK===; "
    "cat /proc/464919/status | grep -E 'State|Threads'; "
    "cat /proc/464918/status | grep -E 'State|Threads'"),
    timeout=90, echo=False)
print(o)
c.close()
