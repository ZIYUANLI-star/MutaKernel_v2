"""Deep progress check: children CPU, unit dir contents, per-case progress."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "echo ===CHILDREN===; "
    "for p in $(pgrep -f '[_]b9_calib_driver_v2'); do "
    "  ps --ppid $p -o pid,etime,%cpu,rss,cmd 2>/dev/null; done; "
    "echo ===TOPCPU===; ps -eo pid,%cpu,etime,cmd --sort=-%cpu | head -6; "
    "echo ===UNIT_FILES===; "
    "ls -la /root/mk_v2_runs/e3_b9_calib/units/L1_P23__float32/ "
    "/root/mk_v2_runs/e3_b9_calib/units/L1_P23__float16/; "
    "echo ===UNIT_CONTENT===; "
    "for f in /root/mk_v2_runs/e3_b9_calib/units/L1_P23__float32/*; do "
    "  echo \"-- $f\"; tail -c 600 $f; echo; done; "
    "echo ===DONE_SAMPLE===; "
    "ls /root/mk_v2_runs/e3_b9_calib/units/L2_P9__float16/"),
    timeout=90, echo=False)
print(o)
c.close()
