import _remote

c = _remote.connect()
_remote.run(c, (
    "ls -la --time-style=+%H:%M /root/mk_v2_runs/e3_c6/; echo ---PS---; "
    "ps aux | grep -v grep | grep -E 'c6|e3_' | head -8; echo ---ERR---; "
    "cat /root/mk_v2_runs/e3_b9_calib/units/L1_P3__float32/*.json 2>/dev/null | head -40; "
    "ls /root/mk_v2_runs/e3_b9_calib/units/L1_P3__float32/ 2>/dev/null; echo ---CAL---; "
    "grep -l 'run_error' /root/mk_v2_runs/e3_b9_calib/calibration_lane*.jsonl 2>/dev/null; "
    "head -c 1500 /root/mk_v2_runs/e3_b9_calib/calibration_lane2.jsonl 2>/dev/null"
), timeout=120)
c.close()
