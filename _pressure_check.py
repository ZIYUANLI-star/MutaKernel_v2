import _remote

c = _remote.connect()
_remote.run(c, (
    "free -g; echo ---OOM---; "
    "cat /sys/fs/cgroup/memory.events 2>/dev/null || "
    "cat /sys/fs/cgroup/memory/memory.failcnt 2>/dev/null; echo ---MAXRSS---; "
    "ps -eo pid,rss,comm --sort=-rss | head -8; echo ---GPU---; "
    "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader; "
    "echo ---DMESG---; dmesg 2>/dev/null | tail -5; echo ---RUNLOG---; "
    "tail -25 /root/mk_v2_runs/e3_b9_calib/units/L1_P3__float32/run.log"
), timeout=120)
c.close()
