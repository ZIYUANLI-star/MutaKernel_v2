"""Check cgroup memory limit, kernel OOM traces, P23 outcomes, driver watchdog."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "echo ===CGROUP===; cat /sys/fs/cgroup/memory.max 2>/dev/null; "
    "cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null; "
    "cat /sys/fs/cgroup/memory.peak 2>/dev/null; "
    "echo ===DMESG===; dmesg -T 2>/dev/null | grep -i -E 'oom|killed process|memory cgroup' | tail -8; "
    "echo ===P23===; grep -h 'L1_P23' /root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl | "
    "/root/miniconda3/bin/python -c \"import sys,json\nfor l in sys.stdin:\n r=json.loads(l)\n print(r['unit'], r['control_status'], 'tol=', r.get('calibrated_tol'), 'rss=', r.get('unit_peak_rss_gb'), 'wall=', r.get('wall_s'), 'exit=', r.get('exit_code'))\"; "
    "echo ===WATCHDOG===; grep -n 'kill\\|SIGKILL\\|rss\\|watchdog' /root/mk_v2/_b9_calib_driver_v2.py | head -20; "
    "echo ===S2_ERRORS===; grep -h '\"wave\": \"v2_post_quantile_fix\"' /root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl | "
    "/root/miniconda3/bin/python -c \"import sys,json\nfrom collections import Counter\nrows=[json.loads(l) for l in sys.stdin]\nst=Counter(r['control_status'] for r in rows)\nprint('stage2 rows so far:', len(rows), dict(st))\nfor r in rows:\n  if r['control_status']!='calibrated_ok': print(' ', r['unit'], r['control_status'], r.get('exit_code'), r.get('wall_s'))\""),
    timeout=90, echo=False)
print(o)
c.close()
