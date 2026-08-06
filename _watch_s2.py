"""Poll B9 stage-2 every 20 min; print S2_ALL_DONE when both lanes finish.

Also raises S2_STALL if drivers vanish while work remains, so the run can
be rescued instead of silently dying.
"""
import time
import _remote

while True:
    try:
        c = _remote.connect()
        _, o, _ = _remote.run(c, (
            "ls /root/mk_v2_runs/e3_b9_calib/B9_CALIB_V2_DONE_LANE0 "
            "/root/mk_v2_runs/e3_b9_calib/B9_CALIB_V2_DONE_LANE1 2>/dev/null; echo ---; "
            "pgrep -c -f '[_]b9_calib_driver_v2' 2>/dev/null; echo ---; "
            "/root/miniconda3/bin/python -c \"import json; "
            "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
            "print('pending', len(q['pending']), 'claimed', len(q['claimed']), "
            "'done', len(q['done']))\"; echo ---; "
            "tail -2 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log"),
            timeout=90, echo=False)
        c.close()
        stamp = time.strftime("%H:%M:%S")
        lines = o.splitlines()
        done0 = "DONE_LANE0" in o
        done1 = "DONE_LANE1" in o
        print("[%s] done0=%s done1=%s | %s" % (
            stamp, done0, done1,
            " | ".join(l for l in lines if l.startswith("pending"))), flush=True)
        if done0 and done1:
            print("S2_ALL_DONE", flush=True)
            break
        # stall detection: no drivers and work remains
        try:
            drv = int([l for l in lines if l.strip().isdigit()][0])
        except (IndexError, ValueError):
            drv = -1
        pending_line = next((l for l in lines if l.startswith("pending")), "")
        if drv == 0 and pending_line and not pending_line.startswith("pending 0"):
            print("S2_STALL drivers=0 with work remaining: %s" % pending_line,
                  flush=True)
    except Exception as exc:  # noqa: BLE001 - keep watcher alive across net blips
        print("[watch error] %r" % exc, flush=True)
    time.sleep(1200)
