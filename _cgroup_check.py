import _remote

c = _remote.connect()
_remote.run(c, (
    "cat /sys/fs/cgroup/memory.max 2>/dev/null; "
    "cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null; "
    "cat /sys/fs/cgroup/memory.current 2>/dev/null; "
    "cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null; "
    "echo ---EVENTS---; cat /sys/fs/cgroup/memory.events 2>/dev/null; "
    "cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null; "
    "echo ---GUARD---; cat /root/mk_v2_runs/e3_b9_calib/guard_b9.sh; "
    "echo ---QUANTILE_HITS---; "
    "grep -c 'quantile' /root/mk_v2_runs/e3_b9_calib/units/*/run.log 2>/dev/null | grep -v ':0' | wc -l; "
    "grep -h 'run_error' /root/mk_v2_runs/e3_b9_calib/calibration_lane*.jsonl | wc -l"
), timeout=120)
c.close()
