"""Remove pause marker; verify lanes actually start under the 105GiB budget."""
import time
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "rm -f /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN && echo MARKER_REMOVED; "
    "ls /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN 2>/dev/null || echo MARKER_GONE"),
    timeout=30, echo=False)
print(o)

time.sleep(80)
_, o, _ = _remote.run(c, (
    "pgrep -af '[_]b9_calib_driver_v2|[r]un_e3_external.py run' | head -6; echo ---; "
    "tail -3 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log; echo ---; "
    "tail -2 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo ---; "
    "tail -2 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log; echo ---; "
    "/root/miniconda3/bin/python -c \"import json; "
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
    "print('pending',len(q['pending']),'claimed',len(q['claimed']),'done',len(q['done'])); "
    "print(json.dumps(q['claimed']))\""),
    timeout=60, echo=False)
print(o)
c.close()
print("UNPAUSE_DONE")
