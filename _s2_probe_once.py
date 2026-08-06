"""One-shot stage-2 probe (run under a hard subprocess timeout)."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "ls /root/mk_v2_runs/e3_b9_calib/B9_CALIB_V2_DONE_LANE0 "
    "/root/mk_v2_runs/e3_b9_calib/B9_CALIB_V2_DONE_LANE1 2>/dev/null; echo ---; "
    "pgrep -c -f '[_]b9_calib_driver_v2'; echo ---; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob\n"
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "err=0\n"
    "seen={}\n"
    "for f in sorted(glob.glob('/root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl')):\n"
    "    for line in open(f):\n"
    "        if line.strip():\n"
    "            r=json.loads(line); seen[r['unit']]=r\n"
    "err=sum(1 for r in seen.values() if r['control_status']=='run_error')\n"
    "print('pending %d claimed %d done %d run_error_latest %d' % "
    "(len(q['pending']), len(q['claimed']), len(q['done']), err))\n"
    "EOF"),
    timeout=90, echo=False)
c.close()
done0 = "DONE_LANE0" in o
done1 = "DONE_LANE1" in o
stat = next((l for l in o.splitlines() if l.startswith("pending")), "?")
drv = next((l.strip() for l in o.splitlines() if l.strip().isdigit()), "?")
print("done0=%s done1=%s drivers=%s | %s" % (done0, done1, drv, stat))
